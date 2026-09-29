"""User Story Generator: prompt versionado, schema e parse da resposta.

Os endpoints POST /api/user-story e /api/user-story/stream (app/main.py) sao
quem chama este modulo.
"""

import logging
import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from anthropic import transform_schema
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from pydantic_core import from_json

from app.providers.anthropic_provider import AnthropicProvider, Completion

logger = logging.getLogger(__name__)

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"
PROMPT_NAME = "user_story_v1"


# Docstrings dos modelos viram descricao no schema enviado ao modelo, por isso
# as notas para quem le o codigo ficam em comentarios, e as descricoes em ingles.


# Um cenario Gherkin. Cada passo e uma lista para comportar os "And".
class AcceptanceCriterion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scenario: str = Field(description="Short scenario name")
    given: list[str] = Field(min_length=1, description="Given steps, without the keyword")
    when: list[str] = Field(min_length=1, description="When steps, without the keyword")
    then: list[str] = Field(min_length=1, description="Then steps, without the keyword")


# O formato que o modelo precisa devolver. As tres partes do "As a X, I want Y,
# so that Z" sao campos separados: o schema garante que nenhuma falta, em vez de
# um regex sobre uma frase.
class UserStory(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    as_a: str = Field(description='The role, without the leading "As a"')
    i_want: str = Field(description='The capability, without the leading "I want"')
    so_that: str = Field(description='The benefit, without the leading "so that"')
    acceptance_criteria: list[AcceptanceCriterion] = Field(min_length=3, max_length=5)
    definition_of_done: list[str] = Field(min_length=1)
    edge_cases: list[str]

    @property
    def statement(self) -> str:
        return f"As a {self.as_a}, I want {self.i_want}, so that {self.so_that}"


# Calculado uma vez: o schema e o mesmo em toda chamada. Restricoes que a API
# nao aceita (min/max de itens) viram texto na descricao, e o Pydantic as
# confere no parse.
USER_STORY_SCHEMA = transform_schema(UserStory)


class InvalidUserStoryError(Exception):
    """A resposta do modelo nao valida contra o schema de UserStory."""


@dataclass(frozen=True)
class Prompt:
    version: str
    text: str


@dataclass(frozen=True)
class UserStoryGeneration:
    story: UserStory
    prompt_version: str
    completion: Completion


def load_prompt(name: str = PROMPT_NAME) -> Prompt:
    """Le o prompt do disco em runtime. O nome do arquivo e a versao."""
    return Prompt(version=name, text=(PROMPTS_DIR / f"{name}.md").read_text(encoding="utf-8"))


def parse_user_story(text: str) -> UserStory:
    """Valida o JSON da resposta contra o schema."""
    try:
        return UserStory.model_validate_json(text)
    except ValidationError as exc:
        raise InvalidUserStoryError(str(exc)) from exc


# Intervalo minimo entre dois snapshots parciais no streaming. Um snapshot por
# trecho de texto seriam centenas de mensagens com o objeto inteiro; a cada
# ~100 ms a tela ainda parece continua (ADR-006).
SNAPSHOT_INTERVAL_SECONDS = 0.1


@dataclass(frozen=True)
class PartialUserStory:
    """O objeto ate onde o JSON chegou. Provisorio: ainda nao validado."""

    data: dict[str, Any]


@dataclass(frozen=True)
class CompletedUserStory:
    """Fim do stream: a story validada, que substitui o parcial."""

    generation: UserStoryGeneration


def parse_partial_user_story(text: str) -> dict[str, Any] | None:
    """Le um JSON incompleto e devolve o que ja da para mostrar.

    Strings abertas entram como estao ("trailing-strings"), para o texto crescer
    na tela em vez de esperar a aspa final. Chaves e valores pela metade ficam de
    fora. Devolve None quando ainda nao ha objeto nenhum.
    """
    try:
        value = from_json(text, allow_partial="trailing-strings")
    except ValueError:
        return None
    return value if isinstance(value, dict) else None


def generate_user_story(
    description: str,
    provider: AnthropicProvider,
    prompt: Prompt | None = None,
) -> UserStoryGeneration:
    """Gera uma user story a partir da descricao do problema."""
    prompt = prompt or load_prompt()
    completion = provider.complete(
        system=prompt.text,
        messages=[{"role": "user", "content": description}],
        output_schema=USER_STORY_SCHEMA,
    )
    return _finish(completion, prompt, streamed=False)


def stream_user_story(
    description: str,
    provider: AnthropicProvider,
    prompt: Prompt | None = None,
    *,
    interval: float = SNAPSHOT_INTERVAL_SECONDS,
    clock: Callable[[], float] = time.monotonic,
) -> Iterator[PartialUserStory | CompletedUserStory]:
    """Gera a user story em streaming.

    Produz snapshots parciais no maximo a cada `interval` segundos e termina com
    a story validada. Se a validacao falhar, levanta InvalidUserStoryError depois
    do ultimo parcial: quem esta na tela ve tudo o que chegou, e o erro.
    """
    prompt = prompt or load_prompt()
    text = ""
    sent: dict[str, Any] | None = None
    last_sent_at = float("-inf")

    for chunk in provider.stream(
        system=prompt.text,
        messages=[{"role": "user", "content": description}],
        output_schema=USER_STORY_SCHEMA,
    ):
        if isinstance(chunk, Completion):
            completion = chunk
            break
        text += chunk
        # O trecho que chega antes do intervalo fecha nao se perde: entra no
        # proximo snapshot, ou no ultimo, logo abaixo.
        if clock() - last_sent_at < interval:
            continue
        snapshot = parse_partial_user_story(text)
        if snapshot and snapshot != sent:
            sent, last_sent_at = snapshot, clock()
            yield PartialUserStory(snapshot)
    else:
        raise RuntimeError("provider stream ended without a Completion")

    final = parse_partial_user_story(completion.text)
    if final and final != sent:
        yield PartialUserStory(final)

    yield CompletedUserStory(_finish(completion, prompt, streamed=True))


def _finish(completion: Completion, prompt: Prompt, *, streamed: bool) -> UserStoryGeneration:
    """Loga os metadados e valida a resposta — igual com e sem streaming."""
    logger.info(
        "user_story generated prompt=%s model=%s input_tokens=%d output_tokens=%d "
        "latency_ms=%d first_token_ms=%s stream=%s",
        prompt.version,
        completion.model,
        completion.input_tokens,
        completion.output_tokens,
        completion.latency_ms,
        completion.first_token_ms,
        streamed,
    )

    # Com recusa ou corte por max_tokens, o JSON pode vir fora do schema ou
    # incompleto; o motivo real e mais util que o erro de validacao.
    if completion.stop_reason in ("refusal", "max_tokens"):
        raise InvalidUserStoryError(
            f"generation stopped early: stop_reason={completion.stop_reason}"
        )

    return UserStoryGeneration(
        story=parse_user_story(completion.text),
        prompt_version=prompt.version,
        completion=completion,
    )
