"""Ponto de entrada da API do PO Copilot."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings

VERSION = "0.1.0"

app = FastAPI(title="PO Copilot API", version=VERSION)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    """Checagem de vida: usada pelo dev.ps1, pela CI, pelo healthcheck da
    Railway e pelo indicador de status na landing page."""
    return {
        "status": "ok",
        "version": VERSION,
        "environment": settings.environment,
    }
