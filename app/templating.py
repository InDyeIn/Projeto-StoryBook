"""Configuração do Jinja e helpers disponíveis em todos os templates."""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from fastapi import Request
from fastapi.templating import Jinja2Templates
from markupsafe import Markup

from app.config import settings
from app.permissions import PERMISSION_GROUPS, PERMISSIONS, ROLE_LABELS
from app.security import csrf_token
from app.services import time_ago
from app.systems import get_path, get_system, list_systems

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


def _json_default(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    return str(value)


def to_json(value: Any) -> Markup:
    """Injeta dados no HTML com segurança dentro de <script>."""
    dumped = json.dumps(value, default=_json_default, ensure_ascii=False)
    dumped = dumped.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    return Markup(dumped)


def format_time(value: datetime | None) -> str:
    if value is None:
        return ""
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone().strftime("%H:%M")


def format_date(value: datetime | None) -> str:
    if value is None:
        return ""
    return value.strftime("%d/%m/%Y")


def request_csrf(request: Request) -> str:
    session_id = getattr(request.state, "session_id", None)
    return csrf_token(session_id) if session_id else ""


templates.env.filters["to_json"] = to_json
templates.env.filters["time_ago"] = time_ago
templates.env.filters["hora"] = format_time
templates.env.filters["data"] = format_date

templates.env.globals.update(
    app_name=settings.app_name,
    app_short_name=settings.app_short_name,
    PERMISSIONS=PERMISSIONS,
    PERMISSION_GROUPS=PERMISSION_GROUPS,
    ROLE_LABELS=ROLE_LABELS,
    get_system=get_system,
    list_systems=list_systems,
    get_path=get_path,
    csrf_for=request_csrf,
)


def render(request: Request, name: str, context: dict | None = None, **kwargs):
    """Atalho que sempre injeta ``request`` e o usuário atual no contexto."""
    data = {"request": request, **(context or {}), **kwargs}
    data.setdefault("user", getattr(request.state, "user", None))
    data.setdefault("csrf_token", request_csrf(request))
    return templates.TemplateResponse(request, name, data)
