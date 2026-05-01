"""Runtime configuration loaded from environment variables.

All env vars are prefixed with ``CRYPTOPIA_`` so they don't collide with the
reverse-proxy / Authelia stack we live behind.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="CRYPTOPIA_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Storage ---
    data_dir: Path = Field(default=Path("./data"))
    database_url: str = Field(default="sqlite+aiosqlite:///./data/cryptopia.db")

    # --- URLs ---
    public_url: str = Field(default="http://localhost:8000")
    base_url: str = Field(default="")

    # --- Authelia forward-auth headers ---
    auth_header_user: str = Field(default="Remote-User")
    auth_header_email: str = Field(default="Remote-Email")
    auth_header_name: str = Field(default="Remote-Name")
    auth_header_groups: str = Field(default="Remote-Groups")
    authelia_url: str = Field(default="https://auth.lynxlinkage.com")
    trust_forwarded: bool = Field(default=True)

    # --- Local dev bypass ---
    dev_auth_user: str = Field(default="")
    dev_auth_email: str = Field(default="")
    dev_auth_name: str = Field(default="")
    dev_auth_groups: str = Field(default="")

    # --- Marimo edit subprocess ---
    edit_idle_timeout: int = Field(default=1800)
    edit_port_range_start: int = Field(default=42000)
    edit_port_range_end: int = Field(default=42999)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def notebooks_dir(self) -> Path:
        return self.data_dir / "notebooks"

    @computed_field  # type: ignore[prop-decorator]
    @property
    def published_dir(self) -> Path:
        return self.data_dir / "published"

    @computed_field  # type: ignore[prop-decorator]
    @property
    def published_static_dir(self) -> Path:
        return self.data_dir / "published_static"

    @computed_field  # type: ignore[prop-decorator]
    @property
    def edit_sessions_dir(self) -> Path:
        return self.data_dir / "edit_sessions"

    def ensure_directories(self) -> None:
        for d in (
            self.data_dir,
            self.notebooks_dir,
            self.published_dir,
            self.published_static_dir,
            self.edit_sessions_dir,
        ):
            d.mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    settings = Settings()
    settings.ensure_directories()
    return settings
