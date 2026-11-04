"""Password hashing and signed bearer tokens for user identity."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from uuid import uuid4

from config.settings import settings
from app.repository.db.remote_repository import UsersRepository


class AuthError(Exception):
    def __init__(self, message: str, status_code: int = 401) -> None:
        self.message = message
        self.status_code = status_code
        super().__init__(message)


def _secret() -> bytes:
    secret = settings.AUTH_SECRET_KEY.get_secret_value()
    if len(secret) < 32:
        raise AuthError("AUTH_SECRET_KEY must contain at least 32 characters", 503)
    return secret.encode("utf-8")


def validate_auth_configuration() -> None:
    """Fail during startup if the signing key is not configured correctly."""
    _secret()


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=2**14, r=8, p=1)
    return f"scrypt${_b64(salt)}${_b64(digest)}"


def _verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, salt_text, digest_text = encoded.split("$", 2)
        if algorithm != "scrypt":
            return False
        salt = base64.urlsafe_b64decode(salt_text + "=" * (-len(salt_text) % 4))
        expected = base64.urlsafe_b64decode(digest_text + "=" * (-len(digest_text) % 4))
        actual = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=2**14, r=8, p=1)
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def _issue_token(user_id: str) -> str:
    now = int(time.time())
    header = _b64(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode())
    payload = _b64(json.dumps({
        "sub": user_id,
        "iat": now,
        "exp": now + max(1, settings.AUTH_TOKEN_TTL_HOURS) * 3600,
    }, separators=(",", ":")).encode())
    signing_input = f"{header}.{payload}".encode("ascii")
    signature = _b64(hmac.new(_secret(), signing_input, hashlib.sha256).digest())
    return f"{header}.{payload}.{signature}"


def authenticate_token(token: str) -> dict:
    try:
        header, payload, signature = token.split(".")
        signing_input = f"{header}.{payload}".encode("ascii")
        expected = _b64(hmac.new(_secret(), signing_input, hashlib.sha256).digest())
        if not hmac.compare_digest(signature, expected):
            raise ValueError("signature")
        claims = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
        if not isinstance(claims.get("sub"), str) or int(claims.get("exp", 0)) <= int(time.time()):
            raise ValueError("claims")
    except AuthError:
        raise
    except Exception as exc:
        raise AuthError("Invalid or expired access token") from exc
    user = UsersRepository().get_by_id(claims["sub"])
    if not user:
        raise AuthError("User no longer exists")
    return {"id": user["id"], "email": user["email"], "created_at": user["created_at"]}


def register(email: str, password: str) -> tuple[dict, str]:
    _secret()
    repo = UsersRepository()
    normalized_email = email.strip().lower()
    if repo.get_by_email(normalized_email):
        raise AuthError("Пользователь с таким email уже зарегистрирован", 409)
    user = repo.create(str(uuid4()), normalized_email, _hash_password(password))
    public_user = {"id": user["id"], "email": user["email"], "created_at": user["created_at"]}
    return public_user, _issue_token(user["id"])


def login(email: str, password: str) -> tuple[dict, str]:
    _secret()
    user = UsersRepository().get_by_email(email.strip().lower())
    if not user or not _verify_password(password, user["password_hash"]):
        raise AuthError("Неверный email или пароль")
    public_user = {"id": user["id"], "email": user["email"], "created_at": user["created_at"]}
    return public_user, _issue_token(user["id"])
