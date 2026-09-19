"""Configuração central da aplicação, lida do ambiente ou do arquivo .env."""

from __future__ import annotations

import os
import secrets
import sys
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

#: True quando rodando dentro do executável empacotado (PyInstaller).
FROZEN = getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS")

#: Onde ficam os arquivos DO PROGRAMA (templates, CSS, JS). Dentro do .exe
#: isto é uma pasta temporária, extraída a cada execução — e só de leitura.
BASE_DIR = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))


def _data_dir() -> Path:
    """Onde ficam os arquivos DO USUÁRIO: banco, uploads e .env.

    Empacotado, nada pode ser gravado ao lado do executável (a pasta do .exe
    costuma ser somente leitura, e no Windows pode ser Arquivos de Programas).
    Então os dados vão para a pasta do usuário e sobrevivem a atualizações.
    """
    if not FROZEN:
        return Path(__file__).resolve().parent.parent

    if sys.platform == "win32":
        raiz = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    elif sys.platform == "darwin":
        raiz = Path.home() / "Library" / "Application Support"
    else:
        raiz = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))

    pasta = raiz / "StoryBook"
    pasta.mkdir(parents=True, exist_ok=True)
    return pasta


DATA_DIR = _data_dir()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=DATA_DIR / ".env",
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
    database_url: str = f"sqlite:///{DATA_DIR / 'storybook.db'}"

    # --- Sessão ---
    # Em produção defina SECRET_KEY no .env (python -c "import secrets;print(secrets.token_urlsafe(48))")
    secret_key: str = secrets.token_urlsafe(48)
    session_cookie: str = "sb_session"
    session_max_age_days: int = 30

    # --- Uploads ---
    upload_dir: Path = DATA_DIR / "uploads"
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
    def static_dir(self) -> Path:
        return BASE_DIR / "app" / "static"

    @property
    def templates_dir(self) -> Path:
        return BASE_DIR / "app" / "templates"

    @property
    def secure_cookies(self) -> bool:
        return self.base_url.startswith("https://")


@lru_cache
def get_settings() -> Settings:
    settings = Settings()

    # Empacotado, a SECRET_KEY padrão é sorteada a cada execução — isso
    # deslogaria todo mundo a cada vez que o aplicativo abrisse. Guardamos uma
    # chave na pasta do usuário. Se alguém definiu a sua própria (variável de
    # ambiente ou .env), respeitamos essa.
    definida_pelo_usuario = "secret_key" in settings.model_fields_set
    placeholder = settings.secret_key.startswith("troque")

    if FROZEN and (not definida_pelo_usuario or placeholder):
        arquivo = DATA_DIR / "secret.key"
        if not arquivo.exists():
            arquivo.write_text(secrets.token_urlsafe(48), encoding="utf-8")
            try:  # melhor esforço: só o dono lê
                arquivo.chmod(0o600)
            except OSError:
                pass
        settings.secret_key = arquivo.read_text(encoding="utf-8").strip()

    return settings


settings = get_settings()
