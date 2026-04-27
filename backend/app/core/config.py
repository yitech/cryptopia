from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    app_name: str = "Cryptopia"
    debug: bool = False

    database_url: str = "postgresql+asyncpg://cryptopia:cryptopia@localhost:5432/cryptopia"

    secret_key: str = "change-me-in-production-use-random-256-bit-key"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24 * 7  # 7 days

    allowed_origins: list[str] = ["http://localhost:5173", "http://localhost:3000"]

    # Jupyter kernel data directory — must contain a registered python3 kernelspec.
    jupyter_data_dir: str = ""

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


@lru_cache
def get_settings() -> Settings:
    return Settings()
