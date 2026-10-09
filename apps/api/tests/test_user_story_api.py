"""Testes de ponta a ponta do POST /api/user-story, com o provider mockado.

Passam pelo FastAPI inteiro — validacao da entrada, rate limit, prompt, parse e
serializacao — e so o modelo e falso: custo zero, sem rede.
"""

import json
import logging
from collections.abc import Iterator
from pathlib import Path
from unittest.mock import create_autospec

import anthropic
import httpx
import pytest
from fastapi import Request
from fastapi.testclient import TestClient

from app.main import (
    CREDIT_EXHAUSTED_DETAIL,
    DAILY_QUOTA_KEY,
    app,
    get_daily_quota,
    get_provider,
    get_rate_limit,
)
from app.providers.anthropic_provider import AnthropicProvider, Completion
from app.rate_limit import RateLimiter, client_ip
from app.user_story import UserStory

FIXTURE = Path(__file__).parent / "fixtures" / "user_story_valid.json"
DESCRIPTION = "Users cannot export the report."


def completion(text: str) -> Completion:
    return Completion(
        text=text,
        model="claude-sonnet-5",
        input_tokens=812,
        output_tokens=433,
        latency_ms=5210,
        stop_reason="end_turn",
    )


@pytest.fixture
def provider() -> AnthropicProvider:
    mock = create_autospec(AnthropicProvider, instance=True)
    mock.complete.return_value = completion(FIXTURE.read_text(encoding="utf-8"))
    return mock


@pytest.fixture
def limiter() -> RateLimiter:
    # Um limiter novo por teste: o global acumularia contagem entre eles.
    return RateLimiter(limit=3, window_seconds=3600)


@pytest.fixture
def quota() -> RateLimiter:
    # A cota global tambem nova por teste, pelo mesmo motivo.
    return RateLimiter(limit=20, window_seconds=24 * 3600)


@pytest.fixture
def client(
    provider: AnthropicProvider, limiter: RateLimiter, quota: RateLimiter
) -> Iterator[TestClient]:
    app.dependency_overrides[get_provider] = lambda: provider
    app.dependency_overrides[get_rate_limit] = lambda: limiter
    app.dependency_overrides[get_daily_quota] = lambda: quota
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_post_returns_a_user_story_that_validates_against_the_schema(
    client: TestClient,
) -> None:
    response = client.post("/api/user-story", json={"description": DESCRIPTION})

    assert response.status_code == 200
    story = UserStory.model_validate(response.json())
    assert story.as_a == "sales manager"
    assert 3 <= len(story.acceptance_criteria) <= 5
    assert story.acceptance_criteria[0].given == [
        "I am on the sales report",
        "I have filtered it to Q3",
    ]


def test_post_sends_the_description_to_the_model(
    client: TestClient, provider: AnthropicProvider
) -> None:
    client.post("/api/user-story", json={"description": f"  {DESCRIPTION}  "})

    messages = provider.complete.call_args.kwargs["messages"]
    assert messages == [{"role": "user", "content": DESCRIPTION}]


def test_post_logs_prompt_version_model_tokens_and_latency(
    client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.INFO, logger="app.user_story"):
        client.post("/api/user-story", json={"description": DESCRIPTION})

    line = next(r.getMessage() for r in caplog.records if r.name == "app.user_story")
    for field in (
        "prompt=user_story_v1",
        "model=claude-sonnet-5",
        "input_tokens=812",
        "output_tokens=433",
        "latency_ms=5210",
    ):
        assert field in line


@pytest.mark.parametrize("description", ["", "   ", "too short", "x" * 4001])
def test_post_rejects_invalid_description(
    client: TestClient, provider: AnthropicProvider, description: str
) -> None:
    response = client.post("/api/user-story", json={"description": description})

    assert response.status_code == 422
    provider.complete.assert_not_called()


def test_model_response_outside_schema_returns_clear_502(
    client: TestClient, provider: AnthropicProvider
) -> None:
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    data["acceptance_criteria"] = data["acceptance_criteria"][:2]
    provider.complete.return_value = completion(json.dumps(data))

    response = client.post("/api/user-story", json={"description": DESCRIPTION})

    assert response.status_code == 502
    assert "not a valid user story" in response.json()["detail"]


def test_rate_limit_returns_429_after_the_limit(
    client: TestClient, provider: AnthropicProvider, limiter: RateLimiter
) -> None:
    for _ in range(limiter.limit):
        assert client.post("/api/user-story", json={"description": DESCRIPTION}).status_code == 200

    response = client.post("/api/user-story", json={"description": DESCRIPTION})

    assert response.status_code == 429
    assert int(response.headers["Retry-After"]) > 0
    assert "Rate limit" in response.json()["detail"]
    # A requisicao barrada nao chega ao modelo, que e o ponto do limite.
    assert provider.complete.call_count == limiter.limit


def test_invalid_request_does_not_spend_the_ip_rate_limit(
    client: TestClient, limiter: RateLimiter
) -> None:
    # Entrada invalida nao chega ao modelo, entao nao gasta nada: nem pune quem
    # errou o formulario, nem protege custo algum.
    for _ in range(limiter.limit + 2):
        assert client.post("/api/user-story", json={"description": "short"}).status_code == 422

    for _ in range(limiter.limit):
        assert client.post("/api/user-story", json={"description": DESCRIPTION}).status_code == 200


def test_rate_limiter_with_limit_zero_blocks_everything() -> None:
    limiter = RateLimiter(limit=0, window_seconds=60)

    assert limiter.check("1.2.3.4") == pytest.approx(60)


def test_release_gives_the_last_slot_back() -> None:
    limiter = RateLimiter(limit=1, window_seconds=60)
    assert limiter.check("1.2.3.4") is None

    limiter.release("1.2.3.4")

    assert limiter.check("1.2.3.4") is None


def test_rate_limit_keys_on_cf_connecting_ip_not_on_x_forwarded_for(
    client: TestClient, limiter: RateLimiter
) -> None:
    # Producao (ADR-007): o X-Forwarded-For comeca pelo que o cliente mandou;
    # trocar esse valor nao pode render uma cota nova.
    for i in range(limiter.limit):
        response = client.post(
            "/api/user-story",
            json={"description": DESCRIPTION},
            headers={"CF-Connecting-IP": "177.95.74.30", "X-Forwarded-For": f"198.51.100.{i}"},
        )
        assert response.status_code == 200

    response = client.post(
        "/api/user-story",
        json={"description": DESCRIPTION},
        headers={"CF-Connecting-IP": "177.95.74.30", "X-Forwarded-For": "198.51.100.99"},
    )
    assert response.status_code == 429

    other_visitor = client.post(
        "/api/user-story",
        json={"description": DESCRIPTION},
        headers={"CF-Connecting-IP": "203.0.113.5"},
    )
    assert other_visitor.status_code == 200, "outro visitante tem a propria contagem"


def test_client_ip_falls_back_to_the_connection_without_cloudflare() -> None:
    request = Request(
        {
            "type": "http",
            "headers": [(b"x-forwarded-for", b"198.51.100.7")],
            "client": ("10.0.0.1", 1),
        }
    )

    assert client_ip(request) == "10.0.0.1"


def test_rate_limiter_frees_the_slot_after_the_window() -> None:
    now = [1000.0]
    limiter = RateLimiter(limit=2, window_seconds=60, clock=lambda: now[0])

    assert limiter.check("1.2.3.4") is None
    assert limiter.check("1.2.3.4") is None
    assert limiter.check("1.2.3.4") == pytest.approx(60)
    assert limiter.check("5.6.7.8") is None, "outro IP tem a propria contagem"

    now[0] += 60
    assert limiter.check("1.2.3.4") is None


# --- cota global diaria e saldo esgotado (ADR-007) ------------------------------


def credit_error(status_code: int, message: str) -> anthropic.APIStatusError:
    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    response = httpx.Response(status_code, request=request)
    return anthropic.APIStatusError(message, response=response, body=None)


def test_daily_quota_blocks_once_reached_whatever_the_ip(
    client: TestClient, provider: AnthropicProvider, quota: RateLimiter
) -> None:
    quota.limit = 2
    for _ in range(2):
        assert client.post("/api/user-story", json={"description": DESCRIPTION}).status_code == 200

    response = client.post("/api/user-story", json={"description": DESCRIPTION})

    assert response.status_code == 429
    assert "Demo quota reached for today" in response.json()["detail"]
    assert "2 generations per day" in response.json()["detail"]
    assert int(response.headers["Retry-After"]) > 0
    assert provider.complete.call_count == 2, "a requisicao barrada nao chega ao modelo"


def test_daily_quota_is_shared_by_every_ip() -> None:
    # A chave e a mesma para todos: nao ha IP que ganhe cota propria.
    quota = RateLimiter(limit=1, window_seconds=24 * 3600)
    assert quota.check(DAILY_QUOTA_KEY) is None
    assert quota.check(DAILY_QUOTA_KEY) is not None


def test_invalid_request_does_not_spend_the_daily_quota(
    client: TestClient, quota: RateLimiter
) -> None:
    quota.limit = 1
    assert client.post("/api/user-story", json={"description": "short"}).status_code == 422

    assert client.post("/api/user-story", json={"description": DESCRIPTION}).status_code == 200


def test_daily_quota_at_zero_blocks_the_first_valid_request(
    client: TestClient, provider: AnthropicProvider, quota: RateLimiter
) -> None:
    # O teste de producao da cota: DAILY_GENERATION_QUOTA=0, sem gastar geracao.
    quota.limit = 0

    response = client.post("/api/user-story", json={"description": DESCRIPTION})

    assert response.status_code == 429
    assert "Demo quota reached for today" in response.json()["detail"]
    assert int(response.headers["Retry-After"]) > 0
    provider.complete.assert_not_called()


def test_request_blocked_by_the_daily_quota_does_not_spend_the_ip_rate_limit(
    client: TestClient, limiter: RateLimiter, quota: RateLimiter
) -> None:
    quota.limit = 0
    for _ in range(limiter.limit + 1):
        assert client.post("/api/user-story", json={"description": DESCRIPTION}).status_code == 429

    quota.limit = 20
    for _ in range(limiter.limit):
        assert client.post("/api/user-story", json={"description": DESCRIPTION}).status_code == 200


@pytest.mark.parametrize(
    "error",
    [
        credit_error(402, "billing_error: payment required"),
        credit_error(400, "Your credit balance is too low to access the Anthropic API."),
    ],
    ids=["402-billing-error", "400-credit-balance"],
)
def test_exhausted_credit_returns_a_clear_message_not_a_generic_error(
    client: TestClient, provider: AnthropicProvider, error: anthropic.APIStatusError
) -> None:
    provider.complete.side_effect = error

    response = client.post("/api/user-story", json={"description": DESCRIPTION})

    assert response.status_code == 503
    assert response.json()["detail"] == CREDIT_EXHAUSTED_DETAIL


def test_other_bad_request_is_still_a_provider_error(
    client: TestClient, provider: AnthropicProvider
) -> None:
    provider.complete.side_effect = credit_error(400, "messages: field required")

    response = client.post("/api/user-story", json={"description": DESCRIPTION})

    assert response.status_code == 502
