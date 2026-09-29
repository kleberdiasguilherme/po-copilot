"""Testes do streaming da user story (US-006, ADR-006), com o provider mockado.

Cobrem o parse de JSON incompleto, o intervalo entre snapshots e o endpoint SSE
de ponta a ponta: ordem dos eventos, erro no meio do stream e rate limit.
"""

import json
import logging
from collections.abc import Iterator
from pathlib import Path
from typing import Any
from unittest.mock import create_autospec

import anthropic
import httpx
import pytest
from fastapi.testclient import TestClient

from app.main import app, get_provider, user_story_rate_limit
from app.providers.anthropic_provider import AnthropicProvider, Completion
from app.rate_limit import RateLimiter
from app.user_story import (
    CompletedUserStory,
    InvalidUserStoryError,
    PartialUserStory,
    UserStory,
    parse_partial_user_story,
    stream_user_story,
)

FIXTURE = Path(__file__).parent / "fixtures" / "user_story_valid.json"
DESCRIPTION = "Users cannot export the report."


def fixture_text() -> str:
    return FIXTURE.read_text(encoding="utf-8")


def completion(text: str, stop_reason: str = "end_turn") -> Completion:
    return Completion(
        text=text,
        model="claude-sonnet-5",
        input_tokens=812,
        output_tokens=433,
        latency_ms=5210,
        stop_reason=stop_reason,
        first_token_ms=1240,
    )


def chunks(text: str, size: int = 7) -> list[str]:
    return [text[i : i + size] for i in range(0, len(text), size)]


def streamed(text: str, stop_reason: str = "end_turn") -> list[str | Completion]:
    return [*chunks(text), completion(text, stop_reason)]


def assert_prefix_of(partial: Any, full: Any) -> None:
    """Tudo o que o parcial mostra tem de ser o comeco do que o final vai ter."""
    if isinstance(partial, dict):
        assert isinstance(full, dict)
        for key, value in partial.items():
            assert key in full, f"chave inventada: {key!r}"
            assert_prefix_of(value, full[key])
    elif isinstance(partial, list):
        assert isinstance(full, list)
        assert len(partial) <= len(full)
        for item, full_item in zip(partial, full, strict=False):
            assert_prefix_of(item, full_item)
    elif isinstance(partial, str):
        assert isinstance(full, str)
        assert full.startswith(partial), f"{partial!r} nao e prefixo de {full!r}"
    else:
        assert partial == full


# --- parse de JSON incompleto ---------------------------------------------------


def tricky_story_json(*, ensure_ascii: bool) -> str:
    # Acentos, aspas escapadas e barra: os cortes no meio de um escape (é,
    # \") sao os que quebrariam um parser ingenuo.
    data = json.loads(fixture_text())
    data["title"] = 'Exportação do relatório "Q3" em CSV\\PDF'
    return json.dumps(data, ensure_ascii=ensure_ascii, indent=2)


@pytest.mark.parametrize(
    "text",
    [fixture_text(), tricky_story_json(ensure_ascii=True), tricky_story_json(ensure_ascii=False)],
    ids=["fixture", "escaped", "unicode"],
)
def test_partial_parse_survives_a_cut_at_any_position(text: str) -> None:
    full = json.loads(text)

    for cut in range(len(text) + 1):
        partial = parse_partial_user_story(text[:cut])
        if partial is None:
            assert not text[:cut].strip(), f"nada lido com {cut} caracteres"
            continue
        assert_prefix_of(partial, full)

    assert parse_partial_user_story(text) == full


def test_partial_parse_shows_an_open_string_as_it_grows() -> None:
    assert parse_partial_user_story('{"title": "Export the rep') == {"title": "Export the rep"}


def test_partial_parse_leaves_out_a_half_written_key() -> None:
    assert parse_partial_user_story('{"title": "Export", "as') == {"title": "Export"}


# --- o gerador de eventos --------------------------------------------------------


def provider_streaming(items: list[str | Completion]) -> AnthropicProvider:
    mock = create_autospec(AnthropicProvider, instance=True)
    mock.stream.side_effect = lambda **_: iter(items)
    return mock


class TickingClock:
    """Relogio falso que anda `step` segundos a cada leitura."""

    def __init__(self, step: float):
        self.step = step
        self.now = 0.0

    def __call__(self) -> float:
        self.now += self.step
        return self.now


def test_stream_ends_with_the_validated_story_after_the_partials() -> None:
    events = list(stream_user_story(DESCRIPTION, provider_streaming(streamed(fixture_text()))))

    *partials, last = events
    assert partials and all(isinstance(event, PartialUserStory) for event in partials)
    assert isinstance(last, CompletedUserStory)
    assert last.generation.story == UserStory.model_validate_json(fixture_text())
    # O ultimo parcial ja e o objeto inteiro: o done nao traz surpresa.
    assert partials[-1].data == json.loads(fixture_text())
    assert last.generation.completion.output_tokens == 433


def test_stream_logs_the_first_token_time(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.INFO, logger="app.user_story"):
        list(stream_user_story(DESCRIPTION, provider_streaming(streamed(fixture_text()))))

    line = next(r.getMessage() for r in caplog.records if r.name == "app.user_story")
    for field in ("first_token_ms=1240", "latency_ms=5210", "stream=True"):
        assert field in line


def test_stream_sends_at_most_one_snapshot_per_interval() -> None:
    items = streamed(fixture_text())
    text_chunks = len(items) - 1

    # Cada chunk chega 20 ms depois do anterior: com intervalo de 100 ms, no
    # maximo um snapshot a cada ~5 chunks, mais o final.
    events = list(
        stream_user_story(
            DESCRIPTION, provider_streaming(items), interval=0.1, clock=TickingClock(0.02)
        )
    )

    partials = [event for event in events if isinstance(event, PartialUserStory)]
    assert 2 <= len(partials) <= text_chunks // 4 + 1


def test_stream_without_throttling_sends_every_change() -> None:
    items = streamed(fixture_text())

    events = list(stream_user_story(DESCRIPTION, provider_streaming(items), interval=0))

    partials = [event for event in events if isinstance(event, PartialUserStory)]
    assert len(partials) > len(items) // 2
    for previous, current in zip(partials, partials[1:], strict=False):
        assert previous.data != current.data, "snapshot repetido"


def test_stream_outside_schema_sends_the_partials_then_raises() -> None:
    data = json.loads(fixture_text())
    data["acceptance_criteria"] = data["acceptance_criteria"] * 2  # 6 cenarios
    text = json.dumps(data)

    events = stream_user_story(DESCRIPTION, provider_streaming(streamed(text)))
    received = []
    with pytest.raises(InvalidUserStoryError):
        for event in events:
            received.append(event)

    # Os seis cenarios chegaram a tela antes do erro: e eles que o erro explica.
    assert isinstance(received[-1], PartialUserStory)
    assert len(received[-1].data["acceptance_criteria"]) == 6


def test_stream_cut_by_max_tokens_reports_the_real_cause() -> None:
    text = fixture_text()[:400]

    with pytest.raises(InvalidUserStoryError, match="max_tokens"):
        list(stream_user_story(DESCRIPTION, provider_streaming(streamed(text, "max_tokens"))))


# --- o endpoint SSE --------------------------------------------------------------


@pytest.fixture
def provider() -> AnthropicProvider:
    return provider_streaming(streamed(fixture_text()))


@pytest.fixture
def limiter() -> RateLimiter:
    return RateLimiter(limit=2, window_seconds=3600)


@pytest.fixture
def client(provider: AnthropicProvider, limiter: RateLimiter) -> Iterator[TestClient]:
    app.dependency_overrides[get_provider] = lambda: provider
    app.dependency_overrides[user_story_rate_limit] = limiter
    yield TestClient(app)
    app.dependency_overrides.clear()


def sse_events(body: str) -> list[tuple[str, dict[str, Any]]]:
    events = []
    for block in body.strip().split("\n\n"):
        fields = dict(line.split(": ", 1) for line in block.splitlines())
        events.append((fields["event"], json.loads(fields["data"])))
    return events


def post_stream(client: TestClient) -> httpx.Response:
    return client.post("/api/user-story/stream", json={"description": DESCRIPTION})


def test_endpoint_emits_partials_then_done_in_order(client: TestClient) -> None:
    response = post_stream(client)

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    events = sse_events(response.text)
    names = [name for name, _ in events]
    assert names[-1] == "done"
    assert set(names[:-1]) == {"partial"}
    story = UserStory.model_validate(events[-1][1]["story"])
    assert story == UserStory.model_validate_json(fixture_text())


def test_endpoint_error_mid_stream_arrives_as_an_event(
    client: TestClient, provider: AnthropicProvider
) -> None:
    def broken(**_: Any) -> Iterator[str]:
        yield from chunks(fixture_text())[:30]
        raise anthropic.APIConnectionError(request=httpx.Request("POST", "https://x"))

    provider.stream.side_effect = broken

    events = sse_events(post_stream(client).text)

    assert events[0][0] == "partial"
    name, data = events[-1]
    assert name == "error"
    assert "could not be reached" in data["detail"]
    assert "done" not in [name for name, _ in events]


def test_endpoint_story_outside_schema_ends_with_error_after_partials(
    client: TestClient, provider: AnthropicProvider
) -> None:
    story = json.loads(fixture_text())
    story["acceptance_criteria"] = story["acceptance_criteria"][:2]
    provider.stream.side_effect = lambda **_: iter(streamed(json.dumps(story)))

    events = sse_events(post_stream(client).text)

    assert events[-2][0] == "partial"
    assert len(events[-2][1]["acceptance_criteria"]) == 2
    name, data = events[-1]
    assert name == "error"
    assert "not a valid user story" in data["detail"]


def test_endpoint_rate_limit_blocks_before_the_stream_opens(
    client: TestClient, provider: AnthropicProvider, limiter: RateLimiter
) -> None:
    for _ in range(limiter.limit):
        assert post_stream(client).status_code == 200

    response = post_stream(client)

    assert response.status_code == 429
    assert response.headers["content-type"].startswith("application/json")
    assert int(response.headers["Retry-After"]) > 0
    assert provider.stream.call_count == limiter.limit


def test_endpoint_shares_the_rate_limit_with_the_non_streaming_endpoint(
    client: TestClient, provider: AnthropicProvider, limiter: RateLimiter
) -> None:
    provider.complete.return_value = completion(fixture_text())
    for _ in range(limiter.limit):
        client.post("/api/user-story", json={"description": DESCRIPTION})

    assert post_stream(client).status_code == 429
    provider.stream.assert_not_called()


def test_endpoint_rejects_invalid_description_before_the_stream_opens(
    client: TestClient, provider: AnthropicProvider
) -> None:
    response = client.post("/api/user-story/stream", json={"description": "short"})

    assert response.status_code == 422
    provider.stream.assert_not_called()
