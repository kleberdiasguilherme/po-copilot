"""Configuracao da API, lida do ambiente ou do .env local."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Variaveis de ambiente da API.

    O .env fica fora do git — veja .env.example para os campos esperados.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    anthropic_api_key: str = ""
    environment: str = "development"


settings = Settings()
