"""Sign backend-to-conversion-service requests without forwarding user roles."""

from __future__ import annotations

import hashlib
import hmac
import time

from config.settings import settings


def make_conversion_proxy_headers(method: str, request_target: str) -> dict[str, str]:
    """Create a short-lived signature proving the request came through backend."""
    secret = settings.AUTH_SECRET_KEY.get_secret_value()
    if len(secret) < 32:
        raise RuntimeError("AUTH_SECRET_KEY must contain at least 32 characters")

    timestamp = str(int(time.time()))
    message = f"{method.upper()}\n{request_target}\n{timestamp}".encode("utf-8")
    signature = hmac.new(secret.encode("utf-8"), message, hashlib.sha256).hexdigest()
    return {
        "X-Backend-Proxy-Timestamp": timestamp,
        "X-Backend-Proxy-Signature": signature,
    }
