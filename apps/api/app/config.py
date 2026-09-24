"""Configuracao da API, lida do ambiente ou do .env local."""

from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_CORS_ORIGINS = "http://localhost:3000"


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

    # Modelo usado em todas as chamadas. Trocar de modelo e decisao registrada
    # (ADR-004), nao detalhe de implementacao: mude aqui, junto com um ADR.
    anthropic_model: str = "claude-sonnet-5"

    environment: str = "development"

    # Origens liberadas no CORS, separadas por virgula. Em producao recebe a
    # URL da Vercel. E uma string, e nao uma lista, porque o painel da Railway
    # so aceita texto — uma lista JSON teria de ser digitada com aspas.
    cors_origins: str = DEFAULT_CORS_ORIGINS

    @property
    def cors_origin_list(self) -> list[str]:
        """As origens do CORS ja separadas e sem espacos em volta."""
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


settings = Settings()
