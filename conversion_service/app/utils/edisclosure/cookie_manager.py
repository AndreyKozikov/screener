"""Centralized cookie management for e-disclosure.ru.

Handles loading, saving, TTL validation, and automatic refresh of
session cookies required to interact with e-disclosure.ru API.
"""

import json
import logging
import os
import time
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger(__name__)

# Default TTL for cookies (2 hours in seconds)
_DEFAULT_COOKIE_TTL_SEC: int = 2 * 60 * 60

# Path to cookies storage
_PACKAGE_DIR: Path = Path(__file__).parent.absolute()
_UTILS_DIR: Path = _PACKAGE_DIR.parent.absolute()
COOKIES_FILE: Path = _UTILS_DIR / "cookies_data.json"


class CookieManager:
    """Manages e-disclosure.ru cookies lifecycle: load, validate, refresh.

    Cookies are stored in a JSON file with a timestamp. When the TTL expires
    or an HTTP 403 is encountered, the manager triggers a refresh via
    CloudflareBypass (DrissionPage) or falls back to manual methods.
    """

    def __init__(
        self,
        cookies_file: Optional[Path] = None,
        ttl_seconds: int = _DEFAULT_COOKIE_TTL_SEC,
    ) -> None:
        self._cookies_file: Path = cookies_file or COOKIES_FILE
        self._ttl_seconds: int = ttl_seconds
        self._cached_cookies: Optional[Dict[str, str]] = None
        self._cached_token: Optional[str] = None
        self._loaded_at: float = 0.0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_cookies_and_token(self, *, force_refresh: bool = False) -> Tuple[Dict[str, str], str]:
        """Return valid cookies and verification token.

        If cookies are expired or missing, triggers an automatic refresh
        using DrissionPage. If automatic refresh fails, falls back to
        loading from the saved file.

        Args:
            force_refresh: If ``True``, bypass TTL check and refresh immediately.

        Returns:
            Tuple of (cookies_dict, verification_token).

        Raises:
            RuntimeError: If no valid cookies could be obtained.
        """
        if not force_refresh and self._is_cache_valid():
            logger.debug("Cookies cache is valid (TTL not expired)")
            return self._cached_cookies, self._cached_token  # type: ignore[return-value]

        # Try loading from file first
        file_cookies, file_token, file_ts = self._load_from_file()
        if file_cookies and file_token and not force_refresh:
            age_seconds = time.time() - file_ts
            if age_seconds < self._ttl_seconds:
                logger.info(
                    "Cookies loaded from file (age: %.0f sec, TTL: %d sec)",
                    age_seconds,
                    self._ttl_seconds,
                )
                self._update_cache(file_cookies, file_token)
                return file_cookies, file_token

        # Cookies are stale or missing — try automatic refresh
        logger.info("Cookies expired or missing — attempting Cloudflare bypass")
        try:
            from app.utils.edisclosure.cloudflare_bypass import CloudflareBypass

            bypass = CloudflareBypass()
            result = bypass.fetch_cookies()
            if result:
                cookies, token = result["cookies"], result["token"]
                self.save_cookies(cookies, token)
                self._update_cache(cookies, token)
                logger.info("Cookies refreshed via DrissionPage bypass")
                return cookies, token
        except Exception as exc:
            logger.warning("Cloudflare bypass failed: %s", exc)

        # Fallback: use whatever we have from file even if expired
        if file_cookies and file_token:
            logger.warning(
                "Using potentially expired cookies from file (age: %.0f sec)",
                time.time() - file_ts,
            )
            self._update_cache(file_cookies, file_token)
            return file_cookies, file_token

        raise RuntimeError(
            f"❌ No valid cookies available. File '{self._cookies_file}' is missing "
            f"or empty. Run Cloudflare bypass manually or use the cookie web form."
        )

    def invalidate(self) -> None:
        """Mark current cookies as invalid (e.g. after receiving HTTP 403).

        The next call to ``get_cookies_and_token`` will trigger a refresh.
        """
        logger.info("Cookies invalidated — will refresh on next access")
        self._cached_cookies = None
        self._cached_token = None
        self._loaded_at = 0.0

    def clear_saved_credentials(self) -> None:
        """Invalidate memory and remove the persisted e-disclosure cookies file."""
        self.invalidate()
        try:
            self._cookies_file.unlink()
            logger.info("Saved e-disclosure credentials removed from %s", self._cookies_file)
        except FileNotFoundError:
            pass

    def save_cookies(
        self,
        cookies: Dict[str, str],
        token: str,
        *,
        extra: Optional[Dict[str, Any]] = None,
    ) -> Path:
        """Persist cookies and token to the JSON file.

        Args:
            cookies: Dictionary of cookie name-value pairs.
            token: ``__RequestVerificationToken`` value.
            extra: Optional extra fields to store alongside cookies.

        Returns:
            Path to the saved file.
        """
        data: Dict[str, Any] = {
            "cookies": cookies,
            "token": token,
            "timestamp": time.time(),
            "datetime": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        if extra:
            data.update(extra)

        self._cookies_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self._cookies_file, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, ensure_ascii=False)

        logger.info("Cookies saved to %s", self._cookies_file)
        return self._cookies_file

    @property
    def cookies_file_path(self) -> Path:
        """Return the path to the cookies JSON file."""
        return self._cookies_file

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _is_cache_valid(self) -> bool:
        """Check whether the in-memory cache is still within TTL."""
        if self._cached_cookies is None or self._cached_token is None:
            return False
        return (time.time() - self._loaded_at) < self._ttl_seconds

    def _update_cache(self, cookies: Dict[str, str], token: str) -> None:
        """Update the in-memory cache."""
        self._cached_cookies = dict(cookies)
        self._cached_token = token
        self._loaded_at = time.time()

    def _load_from_file(self) -> Tuple[Optional[Dict[str, str]], Optional[str], float]:
        """Load cookies from the JSON file on disk.

        Returns:
            Tuple of (cookies, token, timestamp). All ``None``/0 if file
            doesn't exist or is invalid.
        """
        if not self._cookies_file.exists():
            logger.debug("Cookies file not found: %s", self._cookies_file)
            return None, None, 0.0

        try:
            with open(self._cookies_file, "r", encoding="utf-8") as fh:
                data = json.load(fh)
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Failed to read cookies file: %s", exc)
            return None, None, 0.0

        cookies = data.get("cookies")
        token = data.get("token", "")
        timestamp = float(data.get("timestamp", 0))

        if not cookies or not isinstance(cookies, dict):
            return None, None, 0.0

        return cookies, token, timestamp


# ------------------------------------------------------------------
# Singleton
# ------------------------------------------------------------------

_manager: Optional[CookieManager] = None


def get_cookie_manager() -> CookieManager:
    """Return a module-level singleton ``CookieManager`` instance."""
    global _manager
    if _manager is None:
        _manager = CookieManager()
    return _manager
