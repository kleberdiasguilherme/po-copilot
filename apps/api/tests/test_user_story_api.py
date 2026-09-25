"""Testes de ponta a ponta do POST /api/user-story, com o provider mockado.

Passam pelo FastAPI inteiro — validacao da entrada, rate limit, prompt, parse e
serializacao — e so o modelo e falso: custo zero, sem rede.
"""

import json
import logging
from collections.abc import Iterator
from pathlib import Path
from unittest.mock import create_autospec

import pytest
from fastapi.testclient import TestClient

from app.main import app, get_provider, user_story_rate_limit
from app.providers.anthropic_provider import AnthropicProvider, Completion
from app.rate_limit import RateLimiter
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
def client(provider: AnthropicProvider, limiter: RateLimiter) -> Iterator[TestClient]:
    app.dependency_overrides[get_provider] = lambda: provider
    app.dependency_overrides[user_story_rate_limit] = limiter
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


def test_rate_limiter_frees_the_slot_after_the_window() -> None:
    now = [1000.0]
    limiter = RateLimiter(limit=2, window_seconds=60, clock=lambda: now[0])

    assert limiter.check("1.2.3.4") is None
    assert limiter.check("1.2.3.4") is None
    assert limiter.check("1.2.3.4") == pytest.approx(60)
    assert limiter.check("5.6.7.8") is None, "outro IP tem a propria contagem"

    now[0] += 60
    assert limiter.check("1.2.3.4") is None
