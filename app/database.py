"""Engine, sessão e base declarativa do SQLAlchemy."""

from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings

connect_args = {"check_same_thread": False} if settings.is_sqlite else {}

engine = create_engine(
    settings.database_url,
    connect_args=connect_args,
    pool_pre_ping=True,
    echo=False,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


if settings.is_sqlite:

    @event.listens_for(Engine, "connect")
    def _sqlite_pragmas(dbapi_connection, _connection_record) -> None:
        """Liga chaves estrangeiras (desligadas por padrão no SQLite) e WAL.

        Sem isso os ``ondelete="CASCADE"`` do schema seriam ignorados em
        desenvolvimento e o comportamento divergiria do Postgres na VPS.
        """
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.close()


def get_db() -> Iterator[Session]:
    """Dependência do FastAPI: uma sessão por requisição."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Cria as tabelas que ainda não existem (dev). Em produção use Alembic."""
    from app import models  # noqa: F401  (registra os modelos na metadata)

    Base.metadata.create_all(bind=engine)
