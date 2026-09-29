"""Testes do provider com o cliente do SDK falso: confere o que vai e o que volta."""

import time
from collections.abc import Iterator
from types import SimpleNamespace
from unittest.mock import MagicMock

from app.providers.anthropic_provider import AnthropicProvider, Completion


def fake_client() -> MagicMock:
    client = MagicMock()
    client.messages.create.return_value = SimpleNamespace(
        content=[
            SimpleNamespace(type="thinking", thinking=""),
            SimpleNamespace(type="text", text='{"ok": true}'),
        ],
        model="claude-sonnet-5",
        usage=SimpleNamespace(input_tokens=120, output_tokens=45),
        stop_reason="end_turn",
    )
    return client


def test_complete_returns_text_and_metadata() -> None:
    provider = AnthropicProvider(client=fake_client(), model="claude-sonnet-5")

    result = provider.complete("system", [{"role": "user", "content": "hi"}])

    assert result.text == '{"ok": true}'
    assert result.model == "claude-sonnet-5"
    assert result.input_tokens == 120
    assert result.output_tokens == 45
    assert result.stop_reason == "end_turn"
    assert result.latency_ms >= 0


def test_complete_without_schema_sends_no_output_config() -> None:
    client = fake_client()

    AnthropicProvider(client=client).complete("system", [{"role": "user", "content": "hi"}])

    assert "output_config" not in client.messages.create.call_args.kwargs


def test_complete_with_schema_requests_structured_output() -> None:
    client = fake_client()
    schema = {"type": "object", "properties": {}, "additionalProperties": False}

    AnthropicProvider(client=client, model="claude-sonnet-5").complete(
        "system", [{"role": "user", "content": "hi"}], output_schema=schema
    )

    kwargs = client.messages.create.call_args.kwargs
    assert kwargs["model"] == "claude-sonnet-5"
    assert kwargs["system"] == "system"
    assert kwargs["output_config"] == {"format": {"type": "json_schema", "schema": schema}}


def fake_streaming_client(chunks: list[str]) -> MagicMock:
    stream = MagicMock()
    stream.text_stream = iter(chunks)
    stream.get_final_message.return_value = SimpleNamespace(
        content=[SimpleNamespace(type="text", text="".join(chunks))],
        model="claude-sonnet-5",
        usage=SimpleNamespace(input_tokens=120, output_tokens=45),
        stop_reason="end_turn",
    )
    client = MagicMock()
    client.messages.stream.return_value.__enter__.return_value = stream
    return client


def test_stream_yields_text_chunks_then_completion_with_metadata() -> None:
    client = fake_streaming_client(['{"ok"', ": true}"])

    items = list(
        AnthropicProvider(client=client).stream("system", [{"role": "user", "content": "hi"}])
    )

    assert items[:2] == ['{"ok"', ": true}"]
    completion = items[-1]
    assert isinstance(completion, Completion)
    # Os metadados do dashboard de custos (US-018) sobrevivem ao streaming.
    assert completion.text == '{"ok": true}'
    assert completion.model == "claude-sonnet-5"
    assert completion.input_tokens == 120
    assert completion.output_tokens == 45
    assert completion.stop_reason == "end_turn"
    assert completion.latency_ms >= 0


def test_stream_sends_the_same_request_as_complete() -> None:
    client = fake_streaming_client(["{}"])
    schema = {"type": "object", "properties": {}, "additionalProperties": False}

    list(
        AnthropicProvider(client=client, model="claude-sonnet-5").stream(
            "system", [{"role": "user", "content": "hi"}], output_schema=schema
        )
    )

    kwargs = client.messages.stream.call_args.kwargs
    assert kwargs["model"] == "claude-sonnet-5"
    assert kwargs["system"] == "system"
    assert kwargs["output_config"] == {"format": {"type": "json_schema", "schema": schema}}


def test_closing_the_stream_early_closes_the_api_connection() -> None:
    client = fake_streaming_client(["{", "}"])
    items = AnthropicProvider(client=client).stream("system", [{"role": "user", "content": "hi"}])

    next(items)
    items.close()

    client.messages.stream.return_value.__exit__.assert_called_once()


def test_complete_has_no_first_token_time() -> None:
    result = AnthropicProvider(client=fake_client()).complete(
        "system", [{"role": "user", "content": "hi"}]
    )

    assert result.first_token_ms is None


def test_stream_measures_first_token_when_it_arrives_not_after_it_is_consumed() -> None:
    def slow_start() -> Iterator[str]:
        time.sleep(0.05)  # a API demora para mandar o primeiro trecho
        yield "{"
        yield "}"

    client = fake_streaming_client(["{", "}"])
    client.messages.stream.return_value.__enter__.return_value.text_stream = slow_start()

    completion = None
    for item in AnthropicProvider(client=client).stream(
        "system", [{"role": "user", "content": "hi"}]
    ):
        if isinstance(item, Completion):
            completion = item
        else:
            time.sleep(0.2)  # quem consome demora com cada trecho

    assert completion is not None
    assert completion.first_token_ms is not None
    assert 50 <= completion.first_token_ms < 200, "o tempo de consumo nao entra"
    assert completion.latency_ms >= completion.first_token_ms
