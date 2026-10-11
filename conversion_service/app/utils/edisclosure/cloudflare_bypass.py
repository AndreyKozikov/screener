"""Cloudflare bypass for e-disclosure.ru using DrissionPage (CDP).

DrissionPage controls the browser via Chrome DevTools Protocol (CDP)
instead of the WebDriver protocol. This makes the automation
undetectable by Cloudflare's bot-protection system.

The module automatically:
1. Opens e-disclosure.ru in a real Chrome browser
2. Waits for Cloudflare challenge to resolve (if present)
3. Extracts cookies and __RequestVerificationToken
4. Returns them for use in requests.Session

If the automatic challenge bypass times out, the browser window is shown
to the user so they can complete it manually.
"""

import logging
import re
import time
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

_SEARCH_PAGE_URL: str = "https://www.e-disclosure.ru/poisk-po-kompaniyam"
_MAIN_PAGE_URL: str = "https://www.e-disclosure.ru"

# How long to wait for anti-bot challenge to resolve automatically (seconds)
_CHALLENGE_AUTO_TIMEOUT: int = 45

# How long to wait for manual user intervention (seconds)
_CHALLENGE_MANUAL_TIMEOUT: int = 180

# URL path fragments that indicate an anti-bot challenge page
_CHALLENGE_URL_FRAGMENTS: list[str] = [
    "/xpvnsulc",
    "/cdn-cgi/",
    "hcheck=",
    "challenge",
    "back_location=",
]

# HTML content indicators for challenge pages
_CHALLENGE_HTML_INDICATORS: list[str] = [
    "cf-challenge",
    "challenge-running",
    "turnstile",
    "cf-turnstile",
    "Just a moment",
    "Checking your browser",
    "DDoS protection",
    "Проверка браузера",
]

# Expected URL prefixes that confirm we reached the real site
_EXPECTED_URL_PREFIXES: list[str] = [
    "https://www.e-disclosure.ru/poisk-po-kompaniyam",
    "https://www.e-disclosure.ru/portal/",
    "https://e-disclosure.ru/poisk-po-kompaniyam",
    "https://e-disclosure.ru/portal/",
]


class CloudflareBypass:
    """Automated anti-bot bypass for e-disclosure.ru using DrissionPage (CDP).

    Launches a real Chrome browser, navigates to e-disclosure.ru, waits
    for any anti-bot challenge (custom DDoS protection or Cloudflare) to
    clear, then extracts session cookies and CSRF token.
    """

    def __init__(self, *, headless: bool = False) -> None:
        """Initialize the bypass.

        Args:
            headless: Whether to run Chrome headless. Default is ``False``
                because headed mode has a higher success rate against
                anti-bot detection.
        """
        self._headless: bool = headless

    def fetch_cookies(self) -> Optional[Dict[str, Any]]:
        """Open e-disclosure.ru, bypass anti-bot protection, extract cookies.

        Returns:
            Dictionary with ``cookies`` (dict), ``token`` (str),
            ``timestamp`` (float), ``datetime`` (str), and ``url`` (str).
            Returns ``None`` if the bypass completely fails.
        """
        try:
            from DrissionPage import ChromiumPage, ChromiumOptions
        except ImportError:
            logger.error(
                "DrissionPage is not installed. "
                "Install it with: pip install DrissionPage"
            )
            return None

        page: Optional[ChromiumPage] = None
        try:
            options = self._build_options(ChromiumOptions)
            page = ChromiumPage(addr_or_opts=options)

            logger.info("Opening e-disclosure.ru search page...")
            print("[BYPASS] Opening e-disclosure.ru ...", flush=True)
            page.get(_SEARCH_PAGE_URL)

            # Initial delay for redirect chain to start
            time.sleep(3)

            # Wait for anti-bot challenge to resolve
            if not self._wait_for_challenge(page):
                logger.error("Anti-bot challenge was not resolved")
                return None

            # Extra settle time after challenge resolved
            time.sleep(3)

            # Extract cookies
            cookies_dict = self._extract_cookies(page)
            if not cookies_dict:
                logger.error("No cookies extracted after bypass")
                return None

            # Extract CSRF token
            token = self._extract_token(page)

            result: Dict[str, Any] = {
                "cookies": cookies_dict,
                "token": token or "",
                "timestamp": time.time(),
                "datetime": time.strftime("%Y-%m-%d %H:%M:%S"),
                "url": page.url,
            }

            logger.info(
                "Bypass successful: %d cookies, token=%s",
                len(cookies_dict),
                "found" if token else "NOT found",
            )
            print(
                f"[BYPASS] OK: {len(cookies_dict)} cookies, "
                f"token={'found' if token else 'NOT found'}",
                flush=True,
            )
            return result

        except Exception as exc:
            logger.error("Cloudflare bypass error: %s", exc, exc_info=True)
            print(f"[BYPASS] ERROR: {exc}", flush=True)
            return None
        finally:
            if page is not None:
                try:
                    page.quit()
                    logger.debug("Browser closed")
                except Exception:
                    pass

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_options(self, options_class: type) -> Any:
        """Configure ChromiumOptions for stealth browsing."""
        options = options_class()

        if self._headless:
            options.headless()

        # Anti-detection settings
        options.set_argument("--disable-blink-features=AutomationControlled")
        options.set_argument("--disable-gpu")
        options.set_argument("--no-sandbox")
        options.set_argument("--disable-dev-shm-usage")
        options.set_argument("--window-size=1920,1080")
        options.set_argument("--lang=ru-RU")

        # Set a realistic user-agent
        options.set_user_agent(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/130.0.0.0 Safari/537.36"
        )

        return options

    def _has_reached_destination(self, page: Any) -> bool:
        """Check if the browser has reached the real e-disclosure.ru page."""
        try:
            current_url = page.url or ""
        except Exception:
            return False

        for prefix in _EXPECTED_URL_PREFIXES:
            if current_url.startswith(prefix):
                return True
        return False

    def _is_challenge_active(self, page: Any) -> bool:
        """Check whether an anti-bot challenge is currently displayed.

        Uses two heuristics:
        1. URL-based: if the current URL contains challenge path fragments
           or doesn't match expected destination.
        2. HTML-based: if the page HTML contains challenge indicators.
        """
        # Primary check: are we on the expected destination page?
        if self._has_reached_destination(page):
            return False

        # Check URL for challenge fragments
        try:
            current_url = page.url or ""
        except Exception:
            return True

        for fragment in _CHALLENGE_URL_FRAGMENTS:
            if fragment in current_url:
                return True

        # Check HTML content
        try:
            page_html = page.html or ""
            page_title = page.title or ""
        except Exception:
            return True

        html_lower = page_html.lower()
        title_lower = page_title.lower()
        for indicator in _CHALLENGE_HTML_INDICATORS:
            if indicator.lower() in html_lower or indicator.lower() in title_lower:
                return True

        # If URL is not an expected destination and we can't rule out a challenge
        # by the HTML indicators, still treat it as challenge-active (conservative)
        if not current_url.startswith("https://www.e-disclosure.ru/"):
            return True

        return False

    def _wait_for_challenge(self, page: Any) -> bool:
        """Wait for anti-bot challenge to resolve.

        Phase 1: wait up to ``_CHALLENGE_AUTO_TIMEOUT`` for automatic
        resolution (DDoS protection page auto-redirects after verification).
        Phase 2: show instructions and wait for manual user intervention.

        Returns:
            ``True`` if the challenge was resolved, ``False`` otherwise.
        """
        if not self._is_challenge_active(page):
            logger.info("No anti-bot challenge detected — proceeding")
            print("[BYPASS] No challenge detected", flush=True)
            return True

        try:
            current_url = page.url or "unknown"
        except Exception:
            current_url = "unknown"
        logger.info(
            "Anti-bot challenge detected (URL: %s) — waiting for auto-resolve...",
            current_url[:120],
        )
        print(
            f"[BYPASS] Challenge detected. Waiting up to "
            f"{_CHALLENGE_AUTO_TIMEOUT}s for auto-resolve...",
            flush=True,
        )

        # Phase 1: automatic resolution
        deadline = time.time() + _CHALLENGE_AUTO_TIMEOUT
        while time.time() < deadline:
            time.sleep(2.0)
            if not self._is_challenge_active(page):
                logger.info("Anti-bot challenge auto-resolved!")
                print("[BYPASS] Challenge auto-resolved!", flush=True)
                time.sleep(3.0)
                return True

        logger.warning(
            "Auto-resolve timed out after %d seconds",
            _CHALLENGE_AUTO_TIMEOUT,
        )

        # Phase 2: manual intervention
        print("\n" + "=" * 70)
        print("  ANTI-BOT CHALLENGE -- MANUAL INTERVENTION REQUIRED")
        print("=" * 70)
        print("  Browser window is open. Please complete the challenge manually.")
        print(f"  Waiting up to {_CHALLENGE_MANUAL_TIMEOUT} seconds.")
        print("=" * 70 + "\n", flush=True)

        deadline = time.time() + _CHALLENGE_MANUAL_TIMEOUT
        while time.time() < deadline:
            time.sleep(2.0)
            if not self._is_challenge_active(page):
                logger.info("Challenge resolved after manual intervention")
                print("[BYPASS] Challenge resolved after manual intervention!", flush=True)
                time.sleep(3.0)
                return True

        logger.error(
            "Challenge not resolved after %d seconds total",
            _CHALLENGE_AUTO_TIMEOUT + _CHALLENGE_MANUAL_TIMEOUT,
        )
        print("[BYPASS] FAILED: challenge not resolved in time", flush=True)
        return False

    def _extract_cookies(self, page: Any) -> Dict[str, str]:
        """Extract all cookies from the browser."""
        cookies_dict: Dict[str, str] = {}
        try:
            all_cookies = page.cookies()
            for cookie in all_cookies:
                if isinstance(cookie, dict):
                    name = cookie.get("name", "")
                    value = cookie.get("value", "")
                    if name:
                        cookies_dict[name] = value
                else:
                    # DrissionPage may return cookie objects
                    name = getattr(cookie, "name", "")
                    value = getattr(cookie, "value", "")
                    if name:
                        cookies_dict[name] = value
        except Exception as exc:
            logger.warning("Error extracting cookies: %s", exc)

        logger.debug("Extracted %d cookies", len(cookies_dict))
        return cookies_dict

    def _extract_token(self, page: Any) -> Optional[str]:
        """Extract __RequestVerificationToken from the page."""
        try:
            # Try via DOM element
            token_elem = page.ele(
                'xpath://input[@name="__RequestVerificationToken"]',
                timeout=5,
            )
            if token_elem:
                token = token_elem.attr("value")
                if token:
                    logger.debug("Token found via DOM: %s...", token[:30])
                    return token
        except Exception:
            pass

        # Fallback: try via JavaScript
        try:
            token = page.run_js(
                "return document.querySelector("
                "'input[name=__RequestVerificationToken]'"
                ")?.value || '';"
            )
            if token:
                logger.debug("Token found via JS: %s...", token[:30])
                return token
        except Exception:
            pass

        # Fallback: search in raw HTML
        try:
            html_content = page.html
            match = re.search(
                r'name="__RequestVerificationToken"[^>]*value="([^"]+)"',
                html_content,
            )
            if match:
                token = match.group(1)
                logger.debug("Token found via regex: %s...", token[:30])
                return token
        except Exception:
            pass

        logger.warning("__RequestVerificationToken not found on page")
        return None
