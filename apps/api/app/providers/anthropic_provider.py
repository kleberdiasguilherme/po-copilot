"""Toda chamada ao modelo sai deste arquivo.

E a forma minima da interface Provider do ADR-000: uma classe, um metodo. Trocar
ou acrescentar provedor depois significa escrever outra classe com o mesmo
`complete`, sem cacar chamadas ao SDK espalhadas pelo codigo.
"""

import time
from dataclasses import dataclass
from typing import Any

import anthropic
from anthropic.types import MessageParam

from app.config import settings

# Sem streaming, um teto maior arrisca o timeout HTTP do SDK. Uma user story
# cabe com folga.
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
        extra: dict[str, Any] = {}
        if output_schema is not None:
            extra["output_config"] = {"format": {"type": "json_schema", "schema": output_schema}}

        started = time.perf_counter()
        response = self._client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            system=system,
            messages=messages,
            **extra,
        )
        latency_ms = round((time.perf_counter() - started) * 1000)

        return Completion(
            text="".join(block.text for block in response.content if block.type == "text"),
            model=response.model,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            latency_ms=latency_ms,
            stop_reason=response.stop_reason,
        )
