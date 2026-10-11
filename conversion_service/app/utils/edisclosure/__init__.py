"""Edisclosure Cloudflare bypass and cookie management subpackage.

Provides automated Cloudflare challenge bypass using DrissionPage (CDP),
centralized cookie management with TTL, and fallback mechanisms for
manual cookie retrieval.
"""

from app.utils.edisclosure.cookie_manager import CookieManager, get_cookie_manager
from app.utils.edisclosure.cloudflare_bypass import CloudflareBypass

__all__ = [
    "CookieManager",
    "get_cookie_manager",
    "CloudflareBypass",
]
