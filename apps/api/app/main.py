"""Ponto de entrada da API do PO Copilot."""

import json
import logging
from collections.abc import Iterator
from functools import lru_cache
from typing import Any

import anthropic
from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

from app.config import settings
from app.providers.anthropic_provider import AnthropicProvider
from app.rate_limit import RateLimiter, client_ip
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


def get_rate_limit() -> RateLimiter:
    """O limite por IP como dependencia, para os testes trocarem por um novo."""
    return user_story_rate_limit


# A cota global (ADR-007): uma chave so para todos os visitantes, numa janela
# de 24 h. Zera se o processo reiniciar; o saldo pre-pago e o teto atras dela.
daily_quota = RateLimiter(limit=settings.daily_generation_quota, window_seconds=24 * 3600)
DAILY_QUOTA_KEY = "all-visitors"


def get_daily_quota() -> RateLimiter:
    """A cota como dependencia, para os testes trocarem por uma nova."""
    return daily_quota


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
DAILY_QUOTA_DETAIL = (
    "Demo quota reached for today. This is a portfolio prototype running on a small "
    "prepaid balance, so it allows {limit} generations per day across all visitors. "
    "Try again tomorrow."
)
# O estado em que o demo acaba um dia: o credito pre-pago da Anthropic zerou.
CREDIT_EXHAUSTED_DETAIL = (
    "The demo has used up its prepaid API credit, so generation is paused. "
    "This is a portfolio prototype; the rest of the site still works."
)


RATE_LIMIT_DETAIL = (
    "Rate limit reached: {limit} generations per {minutes} minutes. Try again later."
)


def _enforce_limits(rate_limit: RateLimiter, quota: RateLimiter, ip: str) -> None:
    # Chamada dentro do endpoint, e nao como dependencia: so roda depois de a
    # entrada validar e de a chave existir. Os limites existem para limitar
    # gasto, e uma requisicao que nunca chegaria ao modelo nao gasta nada — nem
    # a cota do IP, nem a do dia.
    rate_limit.enforce(
        ip,
        RATE_LIMIT_DETAIL.format(
            limit=rate_limit.limit, minutes=round(rate_limit.window_seconds / 60)
        ),
    )
    try:
        quota.enforce(DAILY_QUOTA_KEY, DAILY_QUOTA_DETAIL.format(limit=quota.limit))
    except HTTPException:
        # Barrada pela cota do dia, a geracao nao acontece: devolve a vez do IP.
        rate_limit.release(ip)
        raise


def _is_credit_exhausted(exc: anthropic.APIError) -> bool:
    """Saldo da Anthropic zerado.

    A API responde 402 `billing_error`. Versoes anteriores respondiam 400 com
    "credit balance is too low" na mensagem; os dois casos contam.
    """
    if not isinstance(exc, anthropic.APIStatusError):
        return False
    if exc.status_code == 402 or getattr(exc, "type", None) == "billing_error":
        return True
    return exc.status_code == 400 and "credit balance" in str(exc).lower()


@app.get("/health")
def health() -> dict[str, str]:
    """Checagem de vida: usada pelo dev.ps1, pela CI, pelo healthcheck do
    Render e pelo indicador de status na landing page — que, no plano gratuito,
    e tambem quem acorda o servidor (ADR-007)."""
    return {
        "status": "ok",
        "version": VERSION,
        "environment": settings.environment,
    }


# TEMPORARIO (US-034): mostra os cabecalhos de IP como chegam do proxy do
# Render e a chave que o limite por IP usaria. Sai antes do merge do #27.
@app.get("/debug/forwarded")
def debug_forwarded(request: Request) -> dict[str, Any]:
    names = ("x-forwarded-for", "true-client-ip", "cf-connecting-ip")
    return {
        "client_host": request.client.host if request.client else None,
        "rate_limit_key": client_ip(request),
        "headers": {name: request.headers.getlist(name) for name in names},
    }


@app.post(
    "/api/user-story",
    response_model=UserStory,
)
def create_user_story(
    request: UserStoryRequest,
    ip: str = Depends(client_ip),  # noqa: B008
    provider: AnthropicProvider = Depends(get_provider),  # noqa: B008
    rate_limit: RateLimiter = Depends(get_rate_limit),  # noqa: B008
    quota: RateLimiter = Depends(get_daily_quota),  # noqa: B008
) -> UserStory:
    """Gera uma user story a partir da descricao de um problema.

    Sincrono de proposito: o SDK e sincrono, e o FastAPI roda endpoints `def`
    num pool de threads, sem travar o event loop.
    """
    _enforce_limits(rate_limit, quota, ip)
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
        if _is_credit_exhausted(exc):
            logger.error("user_story provider credit exhausted: %s", exc)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=CREDIT_EXHAUSTED_DETAIL
            ) from exc
        logger.warning("user_story provider error: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail=PROVIDER_ERROR_DETAIL
        ) from exc


@app.post(
    "/api/user-story/stream",
    response_class=StreamingResponse,
)
def stream_user_story_endpoint(
    request: UserStoryRequest,
    ip: str = Depends(client_ip),  # noqa: B008
    provider: AnthropicProvider = Depends(get_provider),  # noqa: B008
    rate_limit: RateLimiter = Depends(get_rate_limit),  # noqa: B008
    quota: RateLimiter = Depends(get_daily_quota),  # noqa: B008
) -> StreamingResponse:
    """A mesma geracao, em Server-Sent Events (ADR-006).

    Eventos, nesta ordem: `partial` (o objeto ate onde chegou, nao validado),
    repetido; depois `done` (a story validada) ou `error` (`detail`).

    Rate limit, cota diaria, validacao da entrada e falta de chave respondem
    429/422/503 antes do stream abrir: rodam antes de o primeiro byte sair. Dali
    em diante o status ja e 200, e erro so pode viajar como evento.
    """
    _enforce_limits(rate_limit, quota, ip)
    return StreamingResponse(
        _user_story_events(request.description, provider),
        media_type="text/event-stream",
        # Sem isto, um proxy no caminho (o do Render, ADR-007) pode segurar os
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
        if _is_credit_exhausted(exc):
            logger.error("user_story provider credit exhausted: %s", exc)
            yield _sse("error", {"detail": CREDIT_EXHAUSTED_DETAIL})
            return
        logger.warning("user_story provider error: %s", exc)
        yield _sse("error", {"detail": PROVIDER_ERROR_DETAIL})
    except Exception:
        # Qualquer outra falha tambem precisa chegar a tela como erro, e nao
        # como um stream que simplesmente para.
        logger.exception("user_story stream failed")
        yield _sse("error", {"detail": "The generation failed unexpectedly. Try again."})


def _sse(event: str, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
