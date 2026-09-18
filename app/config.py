"""Configuração central da aplicação, lida do ambiente ou do arquivo .env."""

from __future__ import annotations

import secrets
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Aplicação ---
    app_name: str = "StoryBook"
    app_short_name: str = "SB"
    debug: bool = True
    host: str = "127.0.0.1"
    port: int = 8000
    base_url: str = "http://127.0.0.1:8000"

    # --- Banco ---
    # SQLite para desenvolvimento; na VPS troque por:
    # postgresql+psycopg://storybook:senha@localhost:5432/storybook
    database_url: str = f"sqlite:///{BASE_DIR / 'storybook.db'}"

    # --- Sessão ---
    # Em produção defina SECRET_KEY no .env (python -c "import secrets;print(secrets.token_urlsafe(48))")
    secret_key: str = secrets.token_urlsafe(48)
    session_cookie: str = "sb_session"
    session_max_age_days: int = 30

    # --- Uploads ---
    upload_dir: Path = BASE_DIR / "uploads"
    max_upload_mb: int = 8

    # --- Cadastro ---
    allow_public_signup: bool = True

    @property
    def session_max_age_seconds(self) -> int:
        return self.session_max_age_days * 24 * 60 * 60

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")

    @property
    def secure_cookies(self) -> bool:
        return self.base_url.startswith("https://")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
