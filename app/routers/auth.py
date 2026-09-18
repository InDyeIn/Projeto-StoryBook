"""Cadastro, login e logout."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from sqlalchemy import or_, select

from app.config import settings
from app.deps import CurrentUser, DbDep, verify_csrf
from app.models import Presence, Session, User, utcnow
from app.schemas import LoginIn, PresenceIn, ProfileIn, RegisterIn
from app.security import (
    hash_password,
    hash_token,
    needs_rehash,
    new_session_token,
    sign_session,
    unsign_session,
    verify_password,
)
from app.services import public_user

router = APIRouter(tags=["conta"])


def _start_session(response: Response, db, user: User, request: Request) -> None:
    """Cria a sessão no banco e grava o cookie assinado."""
    token = new_session_token()
    session = Session(
        user_id=user.id,
        token_hash=hash_token(token),
        user_agent=(request.headers.get("user-agent") or "")[:255],
        ip=(request.client.host if request.client else None),
        expires_at=Session.default_expiry(settings.session_max_age_days),
    )
    db.add(session)
    user.presence = Presence.ONLINE
    user.last_seen_at = utcnow()
    db.commit()

    response.set_cookie(
        settings.session_cookie,
        sign_session(session.id, token),
        max_age=settings.session_max_age_seconds,
        httponly=True,
        samesite="lax",
        secure=settings.secure_cookies,
        path="/",
    )


@router.post("/api/cadastro")
async def register(payload: RegisterIn, request: Request, response: Response, db: DbDep):
    if not settings.allow_public_signup:
        raise HTTPException(403, "O cadastro público está desativado nesta instância.")

    email = payload.email.lower()
    existing = db.scalar(
        select(User).where(or_(User.email == email, User.username == payload.username))
    )
    if existing:
        raise HTTPException(
            409,
            "Este e-mail já está cadastrado."
            if existing.email == email
            else "Este nome de usuário já está em uso.",
        )

    user = User(
        email=email,
        username=payload.username,
        display_name=payload.display_name,
        password_hash=hash_password(payload.password),
        tagline="Novo por aqui",
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    _start_session(response, db, user, request)
    return {"user": public_user(user), "redirect": "/painel"}


@router.post("/api/entrar")
async def login(payload: LoginIn, request: Request, response: Response, db: DbDep):
    identifier = payload.identifier.lower()
    user = db.scalar(
        select(User).where(or_(User.email == identifier, User.username == identifier))
    )

    # Mesma resposta nos dois casos: não revela quais contas existem.
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(401, "Usuário ou senha incorretos.")

    # Aproveita o login para atualizar o hash se os parâmetros mudaram.
    if needs_rehash(user.password_hash):
        user.password_hash = hash_password(payload.password)

    _start_session(response, db, user, request)
    return {"user": public_user(user), "redirect": "/painel"}


@router.post("/sair", dependencies=[Depends(verify_csrf)])
async def logout_form(request: Request, db: DbDep):
    """Logout pelo botão do menu (formulário comum, sem JavaScript)."""
    _end_session(request, db)
    response = RedirectResponse("/", status_code=303)
    response.delete_cookie(settings.session_cookie, path="/")
    return response


@router.post("/api/sair")
async def logout_api(request: Request, response: Response, db: DbDep):
    _end_session(request, db)
    response.delete_cookie(settings.session_cookie, path="/")
    return {"ok": True, "redirect": "/"}


def _end_session(request: Request, db) -> None:
    raw = request.cookies.get(settings.session_cookie)
    parsed = unsign_session(raw) if raw else None
    if not parsed:
        return
    session = db.get(Session, parsed[0])
    if session is None:
        return
    session.user.presence = Presence.OFFLINE
    db.delete(session)
    db.commit()


@router.get("/api/eu")
async def me(user: CurrentUser):
    return {"user": public_user(user)}


@router.patch("/api/perfil", dependencies=[Depends(verify_csrf)])
async def update_profile(payload: ProfileIn, user: CurrentUser, db: DbDep):
    data = payload.model_dump(exclude_unset=True)

    if "showcase" in data and data["showcase"] is not None:
        data["showcase"] = [block for block in data["showcase"]]

    for key, value in data.items():
        setattr(user, key, value)

    db.commit()
    db.refresh(user)
    return {"user": public_user(user)}


@router.patch("/api/presenca", dependencies=[Depends(verify_csrf)])
async def update_presence(payload: PresenceIn, user: CurrentUser, db: DbDep):
    user.presence = Presence(payload.presence)
    user.last_seen_at = utcnow()
    db.commit()
    return {"presence": user.presence.value}
