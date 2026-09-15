"""Testes da leitura de configuracao."""

from app.config import Settings


def test_cors_origins_splits_on_commas() -> None:
    settings = Settings(cors_origins="https://po-copilot.vercel.app,http://localhost:3000")

    assert settings.cors_origin_list == [
        "https://po-copilot.vercel.app",
        "http://localhost:3000",
    ]


def test_cors_origins_tolerates_spaces_and_trailing_commas() -> None:
    """O painel da Railway convida a digitar com espacos depois da virgula."""
    settings = Settings(cors_origins="https://a.vercel.app, http://localhost:3000, ")

    assert settings.cors_origin_list == [
        "https://a.vercel.app",
        "http://localhost:3000",
    ]


def test_cors_origins_defaults_to_localhost() -> None:
    assert Settings().cors_origin_list == ["http://localhost:3000"]
