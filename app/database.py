"""Engine, sessão e base declarativa do SQLAlchemy."""

from __future__ import annotations

import logging
from collections.abc import Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings

logger = logging.getLogger("storybook.db")

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


def _literal_sql(valor) -> str | None:
    """Converte um valor padrão de coluna em literal SQL, ou None se não der.

    Enums do SQLAlchemy são gravados pelo *nome* do membro — ``str(enum)``
    devolveria "Classe.MEMBRO" e escreveria lixo no banco.
    """
    import enum as _enum

    if valor is None or callable(valor):
        return None
    if isinstance(valor, _enum.Enum):
        return f"'{valor.name}'"
    if isinstance(valor, bool):
        return "1" if valor else "0"
    if isinstance(valor, (int, float)):
        return str(valor)
    if isinstance(valor, str):
        escapado = valor.replace("'", "''")
        return f"'{escapado}'"
    return None


def ensure_columns() -> None:
    """Acrescenta colunas novas a tabelas que já existem.

    ``create_all`` só cria tabelas que faltam — ele não mexe nas que já estão
    lá. Sem isto, quem atualizasse o projeto teria que apagar o banco a cada
    campo novo. Aqui comparamos os modelos com o banco e emitimos apenas os
    ``ALTER TABLE ... ADD COLUMN`` que faltam.

    Cobre o caso simples (coluna nova com valor padrão), que é o que aparece
    no dia a dia deste projeto. Mudança de tipo, renomear e remover continuam
    sendo trabalho do Alembic.
    """
    from sqlalchemy import inspect, text
    from sqlalchemy.schema import CreateColumn

    inspector = inspect(engine)
    tabelas_no_banco = set(inspector.get_table_names())

    with engine.begin() as conexao:
        for tabela in Base.metadata.sorted_tables:
            if tabela.name not in tabelas_no_banco:
                continue  # create_all cuida desta

            existentes = {c["name"] for c in inspector.get_columns(tabela.name)}
            for coluna in tabela.columns:
                if coluna.name in existentes:
                    continue
                if coluna.primary_key:
                    logger.warning(
                        "coluna %s.%s é chave primária e não pode ser adicionada "
                        "depois; recrie o banco",
                        tabela.name,
                        coluna.name,
                    )
                    continue

                definicao = CreateColumn(coluna).compile(engine).string
                # SQLite exige um padrão constante para preencher as linhas
                # que já existem; sem isso ele recusa NOT NULL.
                padrao = coluna.default.arg if coluna.default is not None else None
                literal = _literal_sql(padrao)
                if literal is not None:
                    definicao += f" DEFAULT {literal}"
                elif not coluna.nullable:
                    logger.warning(
                        "coluna %s.%s é obrigatória e não tem padrão; "
                        "adicionada como opcional",
                        tabela.name,
                        coluna.name,
                    )
                    definicao = definicao.replace(" NOT NULL", "")

                conexao.execute(
                    text(f'ALTER TABLE "{tabela.name}" ADD COLUMN {definicao}')
                )
                logger.info("banco: coluna %s.%s adicionada", tabela.name, coluna.name)


def init_db() -> None:
    """Cria as tabelas que faltam e completa as colunas novas (dev).

    Em produção, prefira Alembic — já está nas dependências.
    """
    from app import models  # noqa: F401  (registra os modelos na metadata)

    Base.metadata.create_all(bind=engine)
    ensure_columns()
