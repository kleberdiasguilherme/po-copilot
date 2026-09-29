"""Ponto de entrada da API do PO Copilot."""

import json
import logging
from collections.abc import Iterator
from functools import lru_cache
from typing import Any

import anthropic
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

from app.config import settings
from app.providers.anthropic_provider import AnthropicProvider
from app.rate_limit import RateLimiter
from app.user_story import (
    CompletedUserStory,
    InvalidUserStoryError,
    UserStory,
    generate_user_story,
    stream_user_story,
)

VERSION = "0.1.0"

# Os loggers do uvicorn nao cobrem os do app: sem isto, o log de cada geracao
# (versao do prompt, modelo, tokens, latencia) nao sairia em lugar nenhum.
_app_logger = logging.getLogger("app")
if not _app_logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter("%(levelname)s:     %(name)s %(message)s"))
    _app_logger.addHandler(_handler)
    _app_logger.setLevel(logging.INFO)

logger = logging.getLogger(__name__)

app = FastAPI(title="PO Copilot API", version=VERSION)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Um limite so para os dois endpoints de geracao: usar o de streaming nao
# dobra a cota de ninguem.
user_story_rate_limit = RateLimiter(
    limit=settings.rate_limit_requests,
    window_seconds=settings.rate_limit_window_seconds,
)


class UserStoryRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    # O teto limita tambem o custo de uma chamada: o texto vai inteiro ao modelo.
    description: str = Field(min_length=10, max_length=4000)


@lru_cache
def get_provider() -> AnthropicProvider:
    """Um provider por processo. Os testes trocam por um mock via dependency_overrides."""
    if not settings.anthropic_api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="ANTHROPIC_API_KEY is not configured on the server.",
        )
    return AnthropicProvider()


# As mensagens de erro sao as mesmas nos dois endpoints de geracao.
INVALID_STORY_DETAIL = (
    "The model returned a response that is not a valid user story. Generating again usually works."
)
PROVIDER_ERROR_DETAIL = "The model provider could not be reached. Try again in a moment."


@app.get("/health")
def health() -> dict[str, str]:
    """Checagem de vida: usada pelo dev.ps1, pela CI, pelo healthcheck da
    Railway e pelo indicador de status na landing page."""
    return {
        "status": "ok",
        "version": VERSION,
        "environment": settings.environment,
    }


@app.post(
    "/api/user-story",
    response_model=UserStory,
    dependencies=[Depends(user_story_rate_limit)],
)
def create_user_story(
    request: UserStoryRequest,
    provider: AnthropicProvider = Depends(get_provider),  # noqa: B008
) -> UserStory:
    """Gera uma user story a partir da descricao de um problema.

    Sincrono de proposito: o SDK e sincrono, e o FastAPI roda endpoints `def`
    num pool de threads, sem travar o event loop.
    """
    try:
        return generate_user_story(request.description, provider).story
    except InvalidUserStoryError as exc:
        # Resposta do modelo fora do schema (ADR-005): erro do upstream, nao do
        # cliente, e quase sempre resolvido gerando de novo.
        logger.warning("user_story invalid response: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail=INVALID_STORY_DETAIL
        ) from exc
    except anthropic.APIError as exc:
        logger.warning("user_story provider error: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail=PROVIDER_ERROR_DETAIL
        ) from exc


@app.post(
    "/api/user-story/stream",
    response_class=StreamingResponse,
    dependencies=[Depends(user_story_rate_limit)],
)
def stream_user_story_endpoint(
    request: UserStoryRequest,
    provider: AnthropicProvider = Depends(get_provider),  # noqa: B008
) -> StreamingResponse:
    """A mesma geracao, em Server-Sent Events (ADR-006).

    Eventos, nesta ordem: `partial` (o objeto ate onde chegou, nao validado),
    repetido; depois `done` (a story validada) ou `error` (`detail`).

    Rate limit, validacao da entrada e falta de chave respondem 429/422/503 antes
    do stream abrir: as dependencias rodam antes de o primeiro byte sair. Dali em
    diante o status ja e 200, e erro so pode viajar como evento.
    """
    return StreamingResponse(
        _user_story_events(request.description, provider),
        media_type="text/event-stream",
        # Sem isto, um proxy no caminho (a Railway, na US-034) pode segurar os
        # eventos e entregar tudo de uma vez no fim.
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def _user_story_events(description: str, provider: AnthropicProvider) -> Iterator[str]:
    # Gerador sincrono: o Starlette o consome num pool de threads. Se o cliente
    # desconecta, ele e fechado, e o provider fecha a conexao com a API.
    try:
        for event in stream_user_story(description, provider):
            if isinstance(event, CompletedUserStory):
                yield _sse("done", {"story": event.generation.story.model_dump()})
            else:
                yield _sse("partial", event.data)
    except InvalidUserStoryError as exc:
        logger.warning("user_story invalid response: %s", exc)
        yield _sse("error", {"detail": INVALID_STORY_DETAIL})
    except anthropic.APIError as exc:
        logger.warning("user_story provider error: %s", exc)
        yield _sse("error", {"detail": PROVIDER_ERROR_DETAIL})
    except Exception:
        # Qualquer outra falha tambem precisa chegar a tela como erro, e nao
        # como um stream que simplesmente para.
        logger.exception("user_story stream failed")
        yield _sse("error", {"detail": "The generation failed unexpectedly. Try again."})


def _sse(event: str, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
