"""Ponto de entrada da API do PO Copilot."""

import logging
from functools import lru_cache

import anthropic
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, Field

from app.config import settings
from app.providers.anthropic_provider import AnthropicProvider
from app.rate_limit import RateLimiter
from app.user_story import InvalidUserStoryError, UserStory, generate_user_story

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
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=(
                "The model returned a response that is not a valid user story. "
                "Generating again usually works."
            ),
        ) from exc
    except anthropic.APIError as exc:
        logger.warning("user_story provider error: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The model provider could not be reached. Try again in a moment.",
        ) from exc
