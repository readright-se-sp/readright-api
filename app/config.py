from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Reads backend configuration from .env."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    SUPABASE_URL: str = ""
    SUPABASE_SERVICE_KEY: str = ""
    BACKEND_API_KEY: str = ""
    MAI_BASE_URL: str = "https://readright-mai.reevsan.dev/v1"
    MAI_API_KEY: str = ""
    MAI_CONNECT_TIMEOUT_SECONDS: float = 5.0
    MAI_READ_TIMEOUT_SECONDS: float = 125.0
    MAI_SERVICE_NAME: str = "readright-mai"

    ALLOWED_ORIGINS: list[str] = ["http://localhost:5173"]


@lru_cache
def get_settings() -> Settings:
    """Returns cached Settings singleton — .env read once."""
    return Settings()  # type: ignore[call-arg]
