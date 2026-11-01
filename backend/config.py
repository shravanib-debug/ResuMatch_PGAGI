"""
config.py — Application Settings
=================================
Reads all configuration from environment variables via pydantic-settings.
Single source of truth for config — no hardcoded values in other modules.
"""

from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from .env file."""

    # LLM (via Google AI Studio)
    google_api_key: str = ""
    llm_model: str = "gemini-2.0-flash"

    # Database
    database_url: str = "sqlite+aiosqlite:///./interview.db"

    # Vector Store
    chroma_persist_path: str = "./chroma_db"
    embedding_model: str = "all-MiniLM-L6-v2"

    # Interview Config
    max_questions_per_session: int = 5
    retrieval_top_k: int = 4
    min_similarity_score: float = 0.5

    # CORS: comma-separated browser origins allowed to call this API
    allowed_origins: str = "http://localhost:3000,http://127.0.0.1:3000,http://localhost:3001,http://127.0.0.1:3001"

    # File Upload
    upload_dir: str = "./uploads"
    max_file_size_mb: int = 5

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"  # ignore extra env vars that don't map to fields


@lru_cache()
def get_settings() -> Settings:
    """Cached settings instance — created once, reused everywhere."""
    return Settings()
