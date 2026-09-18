"""Hash de senha e gestão de sessões por cookie."""

from __future__ import annotations

import hashlib
import hmac
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from itsdangerous import BadSignature, URLSafeTimedSerializer

from app.config import settings

_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        return _hasher.verify(stored_hash, password)
    except (VerifyMismatchError, InvalidHashError, ValueError):
        return False


def needs_rehash(stored_hash: str) -> bool:
    try:
        return _hasher.check_needs_rehash(stored_hash)
    except (InvalidHashError, ValueError):
        return True


def new_session_token() -> str:
    """Token opaco entregue ao navegador; o banco guarda só o hash."""
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def tokens_match(candidate: str, stored_hash: str) -> bool:
    return hmac.compare_digest(hash_token(candidate), stored_hash)


# --- Cookie assinado: guarda "<session_id>:<token>" sem expor nada útil ---

_serializer = URLSafeTimedSerializer(settings.secret_key, salt="sb-session")


def sign_session(session_id: str, token: str) -> str:
    return _serializer.dumps({"sid": session_id, "tok": token})


def unsign_session(value: str) -> tuple[str, str] | None:
    try:
        data = _serializer.loads(value, max_age=settings.session_max_age_seconds)
    except (BadSignature, Exception):  # noqa: BLE001 — cookie inválido é só deslogar
        return None
    if not isinstance(data, dict):
        return None
    sid, tok = data.get("sid"), data.get("tok")
    if isinstance(sid, str) and isinstance(tok, str):
        return sid, tok
    return None


def csrf_token(session_id: str) -> str:
    """Token derivado da sessão, validado sem estado extra no banco."""
    return hmac.new(
        settings.secret_key.encode(), f"csrf:{session_id}".encode(), hashlib.sha256
    ).hexdigest()[:32]


def csrf_valid(session_id: str, candidate: str) -> bool:
    return hmac.compare_digest(csrf_token(session_id), candidate or "")
