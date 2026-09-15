"""Testes do endpoint /health."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_returns_ok() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_health_reports_the_environment() -> None:
    """A Railway usa este campo para confirmar que as variaveis chegaram."""
    response = client.get("/health")

    assert response.json()["environment"]
