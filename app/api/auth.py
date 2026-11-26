from datetime import datetime, timedelta, timezone
import secrets

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field, field_validator

from app.core.auth import (
    CurrentUser, dummy_password_hash, get_current_user, normalize_login,
    password_bytes, token_digest, verify_password, verify_request_origin,
)
from app.core.config import get_settings
from app.db.auth import AuthRepository

router = APIRouter(prefix="/api/v1/auth", dependencies=[Depends(verify_request_origin)])


class LoginRequest(BaseModel):
    login: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1, max_length=72, repr=False)

    @field_validator("login")
    @classmethod
    def validate_login(cls, value: str) -> str:
        return normalize_login(value)

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        password_bytes(value)
        return value


def _cookie_options() -> dict:
    settings = get_settings()
    return {"key": settings.auth_cookie_name, "path": "/api/v1", "httponly": True,
            "secure": settings.auth_cookie_secure, "samesite": "lax"}


@router.post("/login", response_model=CurrentUser)
def login(body: LoginRequest, request: Request, response: Response) -> CurrentUser:
    repo = AuthRepository()
    user = repo.find_user(body.login)
    valid = verify_password(body.password, user["password_hash"] if user else dummy_password_hash())
    if not valid or not user or not user["is_active"]:
        raise HTTPException(status_code=401, detail="Неверный логин или пароль")
    token = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(hours=get_settings().auth_session_hours)
    if not repo.create_session(token_digest(token), str(user["id"]), expires_at, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Неверный логин или пароль")
    previous = request.cookies.get(get_settings().auth_cookie_name)
    if previous:
        repo.delete_session(token_digest(previous))
    response.set_cookie(value=token, max_age=get_settings().auth_session_hours * 3600, **_cookie_options())
    response.headers["Cache-Control"] = "no-store"
    return CurrentUser.model_validate(user)


@router.get("/me", response_model=CurrentUser)
def me(response: Response, user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    response.headers["Cache-Control"] = "no-store"
    return user


@router.post("/logout", status_code=204)
def logout(request: Request, response: Response) -> None:
    token = request.cookies.get(get_settings().auth_cookie_name)
    if token:
        AuthRepository().delete_session(token_digest(token))
    response.delete_cookie(**_cookie_options())
    response.headers["Cache-Control"] = "no-store"
