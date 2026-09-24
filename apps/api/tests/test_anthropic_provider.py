"""Testes do provider com o cliente do SDK falso: confere o que vai e o que volta."""

from types import SimpleNamespace
from unittest.mock import MagicMock

from app.providers.anthropic_provider import AnthropicProvider


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
