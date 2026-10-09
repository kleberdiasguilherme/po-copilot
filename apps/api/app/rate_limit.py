"""Rate limiting em memoria: por IP e uma cota global diaria (ADR-007).

Antes de ser requisito funcional, e requisito de custo: cada geracao gasta
credito da Anthropic, e sem limite um unico visitante consome o saldo inteiro.
O limite por IP protege a disponibilidade (um visitante nao toma a cota dos
outros); a cota global protege o dinheiro (nenhum numero de IPs passa dela).

Em memoria, e nao em Redis, de proposito: o Render gratuito roda uma instancia
so, e perder a contagem num restart custa no maximo uma janela extra — com o
saldo pre-pago da Anthropic como teto atras dela. Com mais de uma instancia,
cada uma contaria por conta propria; ai sim vale um store externo.
"""

import math
import threading
import time
from collections import deque
from collections.abc import Callable

from fastapi import HTTPException, Request, status


class RateLimiter:
    """Janela deslizante: no maximo `limit` requisicoes por `window_seconds`."""

    def __init__(
        self,
        limit: int,
        window_seconds: float,
        clock: Callable[[], float] = time.monotonic,
    ):
        self.limit = limit
        self.window_seconds = window_seconds
        self._clock = clock
        self._hits: dict[str, deque[float]] = {}
        # Endpoints sincronos rodam num pool de threads.
        self._lock = threading.Lock()

    def check(self, key: str) -> float | None:
        """Registra uma requisicao. Devolve None se passou, ou os segundos
        ate liberar se estourou o limite."""
        now = self._clock()
        with self._lock:
            hits = self._hits.setdefault(key, deque())
            while hits and hits[0] <= now - self.window_seconds:
                hits.popleft()
            if len(hits) >= self.limit:
                # Com limite 0 a lista fica vazia: nada passa, e a espera e a
                # janela inteira.
                return hits[0] + self.window_seconds - now if hits else self.window_seconds
            hits.append(now)
            self._prune(now)
            return None

    def _prune(self, now: float) -> None:
        # Sem isto, cada IP que ja passou por aqui ficaria no dicionario para sempre.
        expired = [
            key
            for key, hits in self._hits.items()
            if not hits or hits[-1] <= now - self.window_seconds
        ]
        for key in expired:
            del self._hits[key]

    def enforce(self, key: str, detail: str) -> None:
        """Registra uma requisicao, ou levanta 429 com `detail` se estourou."""
        retry_after = self.check(key)
        if retry_after is not None:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=detail,
                headers={"Retry-After": str(max(1, math.ceil(retry_after)))},
            )

    def release(self, key: str) -> None:
        """Desfaz o ultimo registro de `key`: a requisicao contou, mas outra
        barreira a barrou antes de chegar ao modelo."""
        with self._lock:
            hits = self._hits.get(key)
            if hits:
                hits.pop()


# O Render atende atras da Cloudflare, que grava o IP de quem abriu a conexao
# neste cabecalho. Medido em producao (ADR-007): um valor forjado pelo cliente
# faz a Cloudflare recusar a requisicao (erro 1000), entao ele nao chega aqui.
CLIENT_IP_HEADER = "cf-connecting-ip"


def client_ip(request: Request) -> str:
    """O IP do visitante, chave do limite por IP.

    Nao vem do X-Forwarded-For: o Render acrescenta a lista ao que o cliente
    mandou, e o IP real nao e nem o primeiro (forjavel) nem o ultimo (um proxy
    interno do Render). Sem o cabecalho — rodando local, ou se um dia o trafego
    deixar de passar pela Cloudflare — vale o IP da conexao: atras de um proxy
    ele e o mesmo para todos, e o limite fica mais severo, nunca contornavel.
    """
    ip = request.headers.get(CLIENT_IP_HEADER, "").strip()
    if ip:
        return ip
    return request.client.host if request.client else "unknown"
