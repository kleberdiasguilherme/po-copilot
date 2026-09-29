"""Toda chamada ao modelo sai deste arquivo.

E a forma minima da interface Provider do ADR-000: uma classe, dois metodos —
`complete` e `stream`, a mesma chamada com e sem streaming. Trocar ou acrescentar
provedor depois significa escrever outra classe com os mesmos metodos, sem cacar
chamadas ao SDK espalhadas pelo codigo.
"""

import time
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

import anthropic
from anthropic.types import MessageParam

from app.config import settings

# Sem streaming, um teto maior arrisca o timeout HTTP do SDK. Uma user story
# cabe com folga; o mesmo teto vale para `stream`, para as duas saidas serem iguais.
DEFAULT_MAX_TOKENS = 16000


@dataclass(frozen=True)
class Completion:
    """O texto da resposta e os metadados da chamada.

    Os metadados alimentam o dashboard de custos do M3 (US-018): coletar agora
    custa quase nada, reconstruir depois e impossivel.
    """

    text: str
    model: str
    input_tokens: int
    output_tokens: int
    latency_ms: int
    stop_reason: str | None


class AnthropicProvider:
    """Encapsula o cliente da Anthropic."""

    def __init__(self, client: anthropic.Anthropic | None = None, model: str | None = None):
        self._client = client or anthropic.Anthropic(api_key=settings.anthropic_api_key or None)
        self.model = model or settings.anthropic_model

    def complete(
        self,
        system: str,
        messages: list[MessageParam],
        *,
        output_schema: dict[str, Any] | None = None,
        max_tokens: int = DEFAULT_MAX_TOKENS,
    ) -> Completion:
        """Envia uma conversa ao modelo e devolve o texto com os metadados.

        Com `output_schema`, a resposta sai restrita a esse JSON schema
        (structured outputs): o modelo nao consegue gerar JSON fora dele.
        """
        started = time.perf_counter()
        response = self._client.messages.create(
            **self._params(system, messages, output_schema, max_tokens)
        )
        return _completion(response, started)

    def stream(
        self,
        system: str,
        messages: list[MessageParam],
        *,
        output_schema: dict[str, Any] | None = None,
        max_tokens: int = DEFAULT_MAX_TOKENS,
    ) -> Iterator[str | Completion]:
        """A mesma chamada de `complete`, entregue aos pedacos.

        Produz cada trecho de texto (`str`) conforme chega e, por ultimo, um
        `Completion` com o texto inteiro e os metadados — os mesmos de `complete`,
        para o streaming nao apagar tokens e latencia do dashboard de custos.

        Fechar o gerador antes do fim (o cliente desconectou) fecha a conexao com
        a API, e o modelo para de gerar tokens que ninguem vai ler.
        """
        started = time.perf_counter()
        with self._client.messages.stream(
            **self._params(system, messages, output_schema, max_tokens)
        ) as stream:
            yield from stream.text_stream
            response = stream.get_final_message()
        yield _completion(response, started)

    def _params(
        self,
        system: str,
        messages: list[MessageParam],
        output_schema: dict[str, Any] | None,
        max_tokens: int,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            "model": self.model,
            "max_tokens": max_tokens,
            "system": system,
            "messages": messages,
        }
        if output_schema is not None:
            params["output_config"] = {"format": {"type": "json_schema", "schema": output_schema}}
        return params


def _completion(response: Any, started: float) -> Completion:
    """Monta o Completion a partir da mensagem final, com ou sem streaming."""
    return Completion(
        text="".join(block.text for block in response.content if block.type == "text"),
        model=response.model,
        input_tokens=response.usage.input_tokens,
        output_tokens=response.usage.output_tokens,
        latency_ms=round((time.perf_counter() - started) * 1000),
        stop_reason=response.stop_reason,
    )
