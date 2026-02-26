"""Application settings loaded from environment variables."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    QDRANT_URL: str | None = None
    QDRANT_API_KEY: str | None = None
    QDRANT_COLLECTION: str = "mismatch_docs"

    OPENAI_API_KEY: str | None = None
    OPENAI_MODEL: str = "gpt-5-mini"
    OPENAI_EMBEDDINGS_MODEL: str = "text-embedding-3-small"

    ODDS_API_KEY: str | None = None
    KALSHI_API_KEY: str | None = None
    TAVILY_API_KEY: str | None = None

    EDGE_THRESHOLD: float = 0.03

    LANGSMITH_API_KEY: str | None = None
    LANGSMITH_PROJECT: str = "mismatch"
    LANGCHAIN_TRACING_V2: str | None = None

    CORS_ORIGINS: str = "*"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
