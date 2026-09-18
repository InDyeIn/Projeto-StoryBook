"""Configuração dos testes: cada execução usa um banco SQLite temporário."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

TEMP_DB = Path(tempfile.gettempdir()) / "storybook-testes.db"

# Precisa acontecer antes de importar o app: as settings são lidas na importação.
os.environ["DATABASE_URL"] = f"sqlite:///{TEMP_DB}"
os.environ["SECRET_KEY"] = "segredo-de-teste-suficientemente-longo"
os.environ["UPLOAD_DIR"] = tempfile.mkdtemp(prefix="sb-uploads-")

from fastapi.testclient import TestClient  # noqa: E402

from app.database import Base, engine  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(autouse=True)
def banco_limpo():
    """Zera o banco entre os testes para que um não contamine o outro."""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def cliente():
    with TestClient(app) as c:
        yield c


class Sessao:
    """Cliente autenticado com cookies próprios, que reenvia o CSRF nas escritas.

    Cada sessão tem o seu ``TestClient``: um cliente compartilhado teria um
    único pote de cookies, e logar o segundo usuário deslogaria o primeiro —
    tornando impossível testar duas pessoas na mesma mesa.
    """

    def __init__(self, cliente: TestClient, usuario: dict):
        self.c = cliente
        self.usuario = usuario
        self.csrf = self._ler_csrf()

    def _ler_csrf(self) -> str:
        import re

        html = self.c.get("/painel").text
        achado = re.search(r'csrf:\s*"([^"]+)"', html)
        return achado.group(1) if achado else ""

    def _headers(self):
        return {"X-CSRF-Token": self.csrf}

    def post(self, url, json=None, **kw):
        return self.c.post(url, json=json, headers=self._headers(), **kw)

    def patch(self, url, json=None, **kw):
        return self.c.patch(url, json=json, headers=self._headers(), **kw)

    def delete(self, url, **kw):
        return self.c.delete(url, headers=self._headers(), **kw)

    def get(self, url, **kw):
        return self.c.get(url, **kw)


@pytest.fixture
def fazer_usuario():
    """Cria uma conta e devolve uma sessão autenticada independente."""
    contador = {"n": 0}
    abertos: list[TestClient] = []

    def criar(username: str | None = None, nome: str | None = None) -> Sessao:
        contador["n"] += 1
        username = username or f"agente{contador['n']}"

        c = TestClient(app)
        abertos.append(c)
        resposta = c.post(
            "/api/cadastro",
            json={
                "email": f"{username}@teste.com",
                "username": username,
                "display_name": nome or username.title(),
                "password": "senhaforte123",
            },
        )
        assert resposta.status_code == 200, resposta.text
        return Sessao(c, resposta.json()["user"])

    yield criar

    for c in abertos:
        c.close()
