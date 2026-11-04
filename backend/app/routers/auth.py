"""Registration, login and current-user endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field, field_validator

from app.services.auth_service import AuthError, authenticate_token, login, register

router = APIRouter(prefix="/api/auth", tags=["authentication"])


class Credentials(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=10, max_length=128)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        value = value.strip()
        if value.count("@") != 1 or "." not in value.rsplit("@", 1)[-1]:
            raise ValueError("Введите корректный email")
        return value


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict


def _response(result: tuple[dict, str]) -> AuthResponse:
    user, token = result
    return AuthResponse(access_token=token, user=user)


def _http_error(exc: AuthError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail=exc.message)


@router.post("/register", response_model=AuthResponse, status_code=201)
def register_user(credentials: Credentials) -> AuthResponse:
    try:
        return _response(register(str(credentials.email), credentials.password))
    except AuthError as exc:
        raise _http_error(exc) from exc


@router.post("/login", response_model=AuthResponse)
def login_user(credentials: Credentials) -> AuthResponse:
    try:
        return _response(login(str(credentials.email), credentials.password))
    except AuthError as exc:
        raise _http_error(exc) from exc


def get_current_user(authorization: Annotated[str | None, Header()] = None) -> dict:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Требуется вход")
    try:
        return authenticate_token(authorization[7:].strip())
    except AuthError as exc:
        raise _http_error(exc) from exc


@router.get("/me")
def current_user(user: Annotated[dict, Depends(get_current_user)]) -> dict:
    return user
