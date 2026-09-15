"""Ponto de entrada da API do PO Copilot."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

VERSION = "0.1.0"

app = FastAPI(title="PO Copilot API", version=VERSION)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    """Checagem de vida usada pelo dev.ps1, pelo Makefile e pela CI."""
    return {"status": "ok", "version": VERSION}
