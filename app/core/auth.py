from functools import lru_cache
from hashlib import sha256
from typing import Literal
from uuid import UUID

import bcrypt
from fastapi import Depends, HTTPException, Request
from pydantic import BaseModel

from app.core.config import get_settings
from app.db.auth import AuthRepository


class CurrentUser(BaseModel):
    id: UUID
    login: str
    name: str
    role: Literal["registrar", "kb_owner"]


def normalize_login(login: str) -> str:
    value = login.strip().casefold()
    if not value or len(value) > 100:
        raise ValueError("Логин должен содержать от 1 до 100 символов")
    return value


def password_bytes(password: str) -> bytes:
    value = password.encode("utf-8")
    if not value or len(value) > 72:
        raise ValueError("Пароль должен содержать от 1 до 72 байт UTF-8")
    return value


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password_bytes(password), bcrypt.gensalt(rounds=12)).decode("ascii")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password_bytes(password), password_hash.encode("ascii"))
    except (ValueError, UnicodeError):
        return False


@lru_cache(maxsize=1)
def dummy_password_hash() -> str:
    return hash_password("MedTrust dummy password for unknown accounts")


def token_digest(token: str) -> str:
    return sha256(token.encode("utf-8")).hexdigest()


def allowed_origins() -> list[str]:
    origins = [value.strip().rstrip("/") for value in get_settings().cors_origins.split(",") if value.strip()]
    if not origins or any("*" in value or value == "null" for value in origins):
        raise ValueError("CORS_ORIGINS должен содержать конкретные доверенные адреса фронтенда")
    return origins


def verify_request_origin(request: Request) -> None:
    # Require Origin even on login, preventing login CSRF. No side effects on GET.
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        if request.headers.get("origin") not in allowed_origins():
            raise HTTPException(status_code=403, detail="Недоверенный источник запроса")


def get_current_user(request: Request) -> CurrentUser:
    token = request.cookies.get(get_settings().auth_cookie_name)
    if not token or len(token) > 128:
        raise HTTPException(status_code=401, detail="Необходимо войти в систему")
    user = AuthRepository().session_user(token_digest(token))
    if user is None:
        raise HTTPException(status_code=401, detail="Сессия истекла. Войдите снова")
    return CurrentUser.model_validate(user)


def require_kb_owner(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    if user.role != "kb_owner":
        raise HTTPException(status_code=403, detail="Доступ разрешён только руководителю")
    return user
