"""Rate limiting por IP, em memoria.

Antes de ser requisito funcional, e requisito de custo: cada geracao gasta
credito da Anthropic, e sem limite um unico visitante consome o saldo inteiro.

Em memoria, e nao em Redis, de proposito: uma instancia so, e perder a contagem
num restart custa no maximo uma janela extra de requisicoes. Com mais de uma
instancia, cada uma contaria por conta propria — ai sim vale um store externo.
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
                return hits[0] + self.window_seconds - now
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

    def __call__(self, request: Request) -> None:
        """Uso como dependencia do FastAPI: levanta 429 quando estoura."""
        # request.client.host e o IP da conexao. Atras de um proxy (Railway,
        # US-034) ele vira o IP do proxy: o uvicorn precisa rodar com
        # --proxy-headers e --forwarded-allow-ips para trocar pelo do visitante.
        # Ler X-Forwarded-For direto aqui deixaria qualquer um forjar o IP.
        key = request.client.host if request.client else "unknown"
        retry_after = self.check(key)
        if retry_after is not None:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=(
                    f"Rate limit reached: {self.limit} generations per "
                    f"{round(self.window_seconds / 60)} minutes. Try again later."
                ),
                headers={"Retry-After": str(max(1, math.ceil(retry_after)))},
            )
