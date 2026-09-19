"""Ponto de entrada do StoryBook."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from app import __version__
from app.config import settings
from app.database import init_db
from app.deps import get_optional_user
from app.templating import render, templates

logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s  %(levelname)-7s %(name)s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("storybook")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    init_db()
    # Quem sabe o endereço de verdade é quem subiu o servidor (run.py, o
    # uvicorn ou desktop.py) — aqui a porta pode ter mudado.
    logger.info("StoryBook %s iniciado (dados em %s)", __version__, settings.upload_dir.parent)
    yield


app = FastAPI(
    title="StoryBook",
    description="Tabletop virtual e rede social para RPG.",
    version=__version__,
    lifespan=lifespan,
    docs_url="/api/docs" if settings.debug else None,
    redoc_url=None,
)

# Caminho absoluto: empacotado, o diretório de trabalho não é o do programa.
app.mount("/static", StaticFiles(directory=settings.static_dir), name="static")


@app.middleware("http")
async def attach_user(request: Request, call_next):
    """Deixa o usuário logado disponível para os templates sem repetir dependência."""
    request.state.user = None
    request.state.session_id = None
    response = await call_next(request)
    return response


def wants_html(request: Request) -> bool:
    if request.url.path.startswith("/api/"):
        return False
    return "text/html" in request.headers.get("accept", "")


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    # Páginas protegidas mandam o visitante para o login em vez de um JSON cru.
    if exc.status_code == 401 and wants_html(request):
        destino = request.url.path
        return RedirectResponse(f"/entrar?proximo={destino}", status_code=303)

    if wants_html(request) and exc.status_code in (403, 404):
        return render(
            request,
            "erro.html",
            {"status": exc.status_code, "detail": exc.detail},
            status_code=exc.status_code,
        )

    return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)


# --- Rotas ---------------------------------------------------------------

from app.routers import (  # noqa: E402  (evita import circular com templating)
    auth,
    characters,
    mine,
    pages,
    rooms,
    social,
    systems,
    uploads,
    ws,
)

app.include_router(pages.router)
app.include_router(auth.router)
app.include_router(rooms.router)
app.include_router(characters.router)
app.include_router(mine.router)
app.include_router(social.router)
app.include_router(systems.router)
app.include_router(uploads.router)
app.include_router(ws.router)


@app.get("/api/saude", tags=["infra"])
async def health() -> dict:
    return {"ok": True, "versao": __version__}
