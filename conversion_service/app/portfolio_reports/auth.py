"""Validate the shared bearer tokens for report imports."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from typing import Annotated

from fastapi import Header, HTTPException

from conversion_service.app.repository.db.remote_repository import UsersRepository
from conversion_service.config.settings import settings


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def get_current_user(authorization: Annotated[str | None, Header()] = None) -> dict:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Требуется вход")

    secret = settings.AUTH_SECRET_KEY.get_secret_value()
    if len(secret) < 32:
        raise HTTPException(status_code=503, detail="AUTH_SECRET_KEY must contain at least 32 characters")

    try:
        header, payload, signature = authorization[7:].strip().split(".")
        signing_input = f"{header}.{payload}".encode("ascii")
        expected = _b64(hmac.new(secret.encode("utf-8"), signing_input, hashlib.sha256).digest())
        if not hmac.compare_digest(signature, expected):
            raise ValueError("signature")
        claims = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
        if not isinstance(claims.get("sub"), str) or int(claims.get("exp", 0)) <= int(time.time()):
            raise ValueError("claims")
    except Exception as exc:
        raise HTTPException(status_code=401, detail="Invalid or expired access token") from exc

    user = UsersRepository().get_by_id(claims["sub"])
    if not user:
        raise HTTPException(status_code=401, detail="User no longer exists")
    return {"id": user["id"], "email": user["email"], "created_at": user["created_at"]}


__all__ = ["get_current_user"]
