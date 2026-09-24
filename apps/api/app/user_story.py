"""User Story Generator: prompt versionado, schema e parse da resposta.

O endpoint vem em outro PR; este modulo e a parte que ele vai chamar.
"""

import logging
from dataclasses import dataclass
from pathlib import Path

from anthropic import transform_schema
from pydantic import BaseModel, ConfigDict, Field, ValidationError

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
    logger.info(
        "user_story generated prompt=%s model=%s input_tokens=%d output_tokens=%d latency_ms=%d",
        prompt.version,
        completion.model,
        completion.input_tokens,
        completion.output_tokens,
        completion.latency_ms,
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
