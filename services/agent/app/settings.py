"""Application settings loaded from environment variables."""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Qdrant
    QDRANT_URL: str | None = None
    QDRANT_API_KEY: str | None = None
    QDRANT_COLLECTION: str = "mismatch_docs"

    # OpenAI
    OPENAI_API_KEY: str | None = None
    OPENAI_MODEL: str = "gpt-4o-mini"
    OPENAI_EMBEDDINGS_MODEL: str = "text-embedding-3-small"
    OPENAI_EMBEDDINGS_DIMENSIONS: int = 1536

    # External APIs
    ODDS_API_KEY: str | None = None
    ODDS_API_BASE_URL: str = "https://api.the-odds-api.com/v4"

    KALSHI_API_KEY: str | None = None
    KALSHI_EMAIL: str | None = None
    KALSHI_PASSWORD: str | None = None
    KALSHI_API_BASE_URL: str = "https://trading-api.kalshi.com/trade-api/v2"

    TAVILY_API_KEY: str | None = None
    TAVILY_API_BASE_URL: str = "https://api.tavily.com"

    COHERE_API_KEY: str | None = None

    # Thresholds
    EDGE_THRESHOLD: float = 0.03

    # LangSmith
    LANGSMITH_API_KEY: str | None = None
    LANGSMITH_PROJECT: str = "mismatch"
    LANGCHAIN_TRACING_V2: str | None = None

    # Data paths
    RAW_DATA_DIR: Path = Path("../../data/raw")
    PROCESSED_DATA_PATH: Path = Path("data/processed/docs.jsonl")

    # Server
    CORS_ORIGINS: str = "*"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
