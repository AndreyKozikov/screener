"""Visible-browser workflow for e-disclosure events and emission documents.

The browser uses an ordinary Selenium session. If e-disclosure presents a
verification challenge, the user can complete it in the visible window and
the downloader continues without copying cookies or switching to a terminal.
The same session is used for company search, the emission-documents page and
file downloads. An explicit Forbidden/rate-limit response stops the run so the
service can checkpoint completed events without continuing to hit the blocked
session. The dedicated Chrome profile lives in
``conversion_service/.edisclosure_browser_profile`` and is removed after an
explicit Forbidden response.
"""

import base64
import binascii
import html
import json
import re
import shutil
import threading
from contextlib import ExitStack
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple
from urllib.parse import parse_qs, urlencode, urljoin, urlparse


_SEARCH_PAGE_URL = "https://www.e-disclosure.ru/poisk-po-kompaniyam"
_SEARCH_API_URL = "https://www.e-disclosure.ru/api/search/companies"
_COMPANY_PAGE_URL = "https://www.e-disclosure.ru/portal/company.aspx"
_EVENT_PAGE_URL = "https://www.e-disclosure.ru/portal/event.aspx"
_EVENTS_API_URL = "https://www.e-disclosure.ru/api/events/page"
_FILES_PAGE_URL = "https://www.e-disclosure.ru/portal/files.aspx"
_MAIN_PAGE_URL = "https://www.e-disclosure.ru"
_INITIAL_WAIT_SECONDS = 20
_CHALLENGE_WAIT_SECONDS = 300
_EVENT_PAGE_BATCH_SIZE = 5
_EVENT_PAGE_MIN_INTERVAL_SECONDS = 1.5
_BROWSER_LOCK = threading.Lock()

_CHALLENGE_MARKERS = (
    "cf-challenge",
    "cf-turnstile",
    "challenge-running",
    "checking your browser",
    "just a moment",
    "проверка браузера",
    "ddos protection",
)
_CHALLENGE_URL_MARKERS = ("/cdn-cgi/", "/xpvnsulc", "hcheck=", "back_location=")

_PAGE_FETCH_JS = r"""
const [url, method, body, contentType, binary, done] = arguments;
const headers = {
    "Accept": binary
        ? "*/*"
        : "application/json, text/javascript, */*; q=0.01",
};
if (!binary) headers["X-Requested-With"] = "XMLHttpRequest";
if (contentType) headers["Content-Type"] = contentType;
const options = { method: method, credentials: "same-origin", headers: headers };
if (body) options.body = body;
fetch(url, options).then(async response => {
    const responseContentType = response.headers.get("Content-Type") || "";
    const disposition = response.headers.get("Content-Disposition") || "";
    if (binary) {
        const blob = await response.blob();
        const dataUrl = await new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onload = () => resolve(String(reader.result || ""));
            reader.onerror = () => reject(reader.error);
            reader.readAsDataURL(blob);
        });
        const commaIndex = dataUrl.indexOf(",");
        done({
            status: response.status,
            contentType: responseContentType,
            disposition: disposition,
            body: commaIndex >= 0 ? dataUrl.slice(commaIndex + 1) : ""
        });
    } else {
        done({
            status: response.status,
            contentType: responseContentType,
            disposition: disposition,
            body: await response.text()
        });
    }
}).catch(error => done({error: String(error)}));
"""


def _detect_protection(value: str) -> Optional[str]:
    """Возвращает маркер антибот-страницы e-disclosure, если он найден."""
    from conversion_service.app.utils.emission_documents_parser import (
        detect_edisclosure_protection,
    )
    return detect_edisclosure_protection(value)


def _plain_page_text(value: str) -> str:
    """Convert either HTML or visible browser text into readable lines."""
    text = html.unescape(value or "")
    text = re.sub(r"(?i)<br\s*/?>", "\n", text)
    text = re.sub(r"(?i)</(?:p|div|h[1-6]|tr|li|pre)\s*>", "\n", text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = text.replace("\xa0", " ")
    return re.sub(r"[ \t]+", " ", text).strip()


def _forbidden_report_fields(value: str) -> Dict[str, Optional[str]]:
    text = _plain_page_text(value)
    fields: Dict[str, Optional[str]] = {}
    for label, key in (
        ("Datetime", "datetime"),
        ("IP", "ip"),
        ("ID", "report_id"),
        ("Origin", "origin"),
    ):
        match = re.search(
            rf"(?im)^\s*{re.escape(label)}\s*:\s*(.+?)\s*$",
            text,
        )
        if not match:
            match = re.search(
                rf"(?i)\b{re.escape(label)}\s*:\s*(.+?)"
                r"(?=\s+(?:Datetime|IP|ID|Origin)\s*:|$)",
                text,
            )
        fields[key] = match.group(1).strip() if match else None
    return fields


def _is_forbidden_response(status: Optional[int], value: str) -> bool:
    text = _plain_page_text(value)
    lowered = text.lower()
    raw_lowered = (value or "").lower()
    has_challenge = any(
        marker in lowered or marker in raw_lowered
        for marker in (*_CHALLENGE_MARKERS, *_CHALLENGE_URL_MARKERS)
    )
    has_forbidden_heading = bool(re.search(r"(?im)^\s*#?\s*forbidden\b", text))
    has_report_fields = all(
        _forbidden_report_fields(text).get(key)
        for key in ("datetime", "ip", "report_id", "origin")
    )
    return (
        status == 429
        or (status == 403 and not has_challenge)
        or has_forbidden_heading
        or ("forbidden" in lowered and has_report_fields)
    )


class EdisclosureAccessBlockedError(RuntimeError):
    """Raised when e-disclosure explicitly blocks the current session."""

    def __init__(
        self,
        *,
        status: Optional[int],
        response_text: str,
        url: str,
        failed_guid: Optional[str] = None,
        partial_texts: Optional[Dict[str, Optional[str]]] = None,
    ) -> None:
        fields = _forbidden_report_fields(response_text)
        self.support_report: Dict[str, Any] = {
            **fields,
            "url": url,
            "http_status": status or 403,
            "report_text": _plain_page_text(response_text),
        }
        self.failed_guid = failed_guid
        self.status = status
        self.partial_texts = dict(partial_texts or {})
        self.partial_events: List[Dict[str, Optional[str]]] = []
        self.checkpoint_path: Optional[str] = None

        report_id = fields.get("report_id")
        if status == 429:
            message = "e-disclosure ограничил частоту запросов (HTTP 429); загрузка остановлена."
        else:
            message = "e-disclosure вернул Forbidden; запросы из этой сессии остановлены."
        if report_id:
            message += f" ID отчёта: {report_id}."
        if status == 429:
            message += " Частотное ограничение не сбрасывается автоматически; checkpoint сохранён."
        else:
            message += (
                " Уже загруженные события сохранены; сервис очистит авторизационное "
                "состояние и попробует продолжить. При исчерпании повторов checkpoint "
                "останется для следующего запуска."
            )
        if status != 429:
            message += " Поле support_report.report_text можно передать в поддержку e-disclosure."
        super().__init__(message)


class EdisclosureBrowserSession:
    """Search companies and download events/documents through visible Chrome."""

    def __init__(self) -> None:
        self._driver: Any = None
        self._profile_path: Optional[Path] = None
        self._delete_profile_on_cleanup = False
        self._auth_cleanup_done = False
        self._lock_acquired = False

    def __enter__(self) -> "EdisclosureBrowserSession":
        _BROWSER_LOCK.acquire()
        self._lock_acquired = True
        try:
            self._launch_driver()
            return self
        except Exception:
            try:
                self._quit_driver()
            except Exception:
                # Preserve the startup error; shutdown is best-effort here.
                pass
            finally:
                self._release_browser_lock()
            raise

    def _launch_driver(self) -> None:
        try:
            from selenium import webdriver
            from selenium.webdriver.chrome.options import Options
        except ImportError as exc:
            raise RuntimeError(
                "Для браузерной загрузки установите зависимости conversion_service "
                "из requirements.txt (включая selenium)."
            ) from exc

        options = Options()
        options.page_load_strategy = "eager"
        options.add_argument("--start-maximized")
        options.add_argument("--lang=ru-RU")

        service_dir = Path(__file__).resolve().parents[3]
        default_profile_candidate = service_dir / ".edisclosure_browser_profile"
        default_profile = default_profile_candidate.resolve()
        profile_path = default_profile
        self._profile_path = profile_path
        is_reparse_point = default_profile_candidate.is_symlink()
        is_junction = getattr(default_profile_candidate, "is_junction", lambda: False)()
        self._delete_profile_on_cleanup = (
            profile_path == default_profile
            and default_profile.is_relative_to(service_dir)
            and not is_reparse_point
            and not is_junction
        )
        profile_path.mkdir(parents=True, exist_ok=True)
        options.add_argument(f"--user-data-dir={profile_path}")

        self._driver = webdriver.Chrome(options=options)
        self._driver.set_page_load_timeout(60)
        self._driver.set_script_timeout(60)

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        try:
            if isinstance(exc, EdisclosureAccessBlockedError) and exc.status != 429:
                self.clear_authorization_data(exc)
            else:
                self._quit_driver()
        finally:
            self._release_browser_lock()

    def clear_authorization_data(
        self,
        error: Optional[EdisclosureAccessBlockedError] = None,
    ) -> Dict[str, Any]:
        """Clear e-disclosure browser and script credentials after a block."""
        if self._auth_cleanup_done:
            return error.support_report.get("cleanup", {}) if error else {}

        errors: List[str] = []
        cleared_origins: List[str] = []
        browser_closed = True
        driver = self._driver
        if driver is not None:
            for origin in ("https://www.e-disclosure.ru", "https://e-disclosure.ru"):
                try:
                    driver.execute_cdp_cmd(
                        "Storage.clearDataForOrigin",
                        {"origin": origin, "storageTypes": "all"},
                    )
                    cleared_origins.append(origin)
                except Exception as exc:
                    errors.append(f"browser storage ({origin}): {exc}")
            try:
                driver.quit()
            except Exception as exc:
                errors.append(f"Chrome shutdown: {exc}")
                browser_closed = False
            finally:
                self._driver = None

        profile_removed = False
        if self._delete_profile_on_cleanup and self._profile_path is not None:
            try:
                shutil.rmtree(self._profile_path, ignore_errors=False)
                profile_removed = True
            except FileNotFoundError:
                profile_removed = True
            except Exception as exc:
                errors.append(f"dedicated Chrome profile: {exc}")

        script_auth_cleared = False
        try:
            from conversion_service.app.utils.edisclosure_utils import clear_edisclosure_auth_state

            script_errors = clear_edisclosure_auth_state()
            errors.extend(script_errors)
            script_auth_cleared = not script_errors
        except Exception as exc:
            errors.append(f"script auth state: {exc}")

        cleanup_result = {
            "site_storage_cleared": (
                len(cleared_origins) == 2 or profile_removed
            ),
            "browser_closed": browser_closed,
            "dedicated_browser_profile_removed": profile_removed,
            "script_auth_data_cleared": script_auth_cleared,
            "errors": errors,
        }
        self._auth_cleanup_done = all(
            cleanup_result[key]
            for key in ("site_storage_cleared", "browser_closed", "script_auth_data_cleared")
        )
        if error is not None:
            error.support_report["cleanup"] = cleanup_result
        return cleanup_result

    def restart_after_block(self, error: EdisclosureAccessBlockedError) -> bool:
        """Clear a blocked session and start a fresh browser for checkpoint resume."""
        if error.status == 429:
            return False
        cleanup = self.clear_authorization_data(error)
        if not all(
            cleanup.get(key, False)
            for key in ("site_storage_cleared", "browser_closed", "script_auth_data_cleared")
        ):
            cleanup["restart_error"] = (
                "Очистка состояния завершилась не полностью; повторный запуск отменён."
            )
            error.support_report["cleanup"] = cleanup
            return False
        try:
            self._launch_driver()
            self._auth_cleanup_done = False
            return True
        except Exception as exc:
            try:
                self._quit_driver()
            except Exception as shutdown_exc:
                error.support_report.setdefault("cleanup", {}).setdefault("errors", []).append(
                    f"Chrome shutdown after restart failure: {shutdown_exc}"
                )
            cleanup = error.support_report.get("cleanup", {})
            cleanup["restart_error"] = str(exc)
            if self._delete_profile_on_cleanup and self._profile_path is not None:
                try:
                    shutil.rmtree(self._profile_path, ignore_errors=True)
                    cleanup["dedicated_browser_profile_removed"] = True
                except Exception as cleanup_exc:
                    cleanup.setdefault("errors", []).append(
                        f"dedicated Chrome profile after restart failure: {cleanup_exc}"
                    )
            error.support_report["cleanup"] = cleanup
            return False

    def _quit_driver(self) -> None:
        if self._driver is None:
            return
        try:
            self._driver.quit()
        finally:
            self._driver = None

    def _release_browser_lock(self) -> None:
        if self._lock_acquired:
            _BROWSER_LOCK.release()
            self._lock_acquired = False

    def resolve_company_id_by_inn(self, inn: str) -> int:
        """Find a company's portal ID using the site's search page."""
        from selenium.webdriver.common.by import By

        driver = self._require_driver()
        driver.get(_SEARCH_PAGE_URL)
        field = self._wait_for_element(By.ID, "textfield", "поле поиска компании")
        field.clear()
        field.send_keys(inn)
        driver.find_element(By.ID, "sendButton").click()

        links = self._wait_for_elements(
            By.CSS_SELECTOR,
            "a[href*='company.aspx?id=']",
            "результаты поиска компании",
        )
        for link in links:
            href = link.get_attribute("href") or ""
            company_id = parse_qs(urlparse(href).query).get("id", [None])[0]
            if company_id and company_id.isdigit():
                return int(company_id)
        raise RuntimeError(f"В результатах поиска не найден ID компании для ИНН {inn}.")

    def list_company_event_years(self, company_id: int) -> List[int]:
        """Read the available event years from the company's portal page."""
        driver = self._require_driver()
        driver.get(f"{_COMPANY_PAGE_URL}?id={company_id}")
        value = self._wait_for_element(
            "id", "EventsYears", "список годов событий на странице компании"
        ).get_attribute("value") or ""
        years: set[int] = set()
        for part in value.split(","):
            try:
                years.add(int(part.strip()))
            except ValueError:
                continue
        return sorted(years)

    def fetch_emitent_year_events(
        self,
        *,
        company_id: int,
        api_year: int,
        boundary_date: str,
        skip_pseudo_guids: Optional[Set[str]] = None,
    ) -> List[Dict[str, Optional[str]]]:
        """Load one year of events and event text through the browser session."""
        try:
            boundary = datetime.strptime(boundary_date, "%Y-%m-%d").date()
        except (ValueError, TypeError):
            return []

        driver = self._require_driver()
        company_url = f"{_COMPANY_PAGE_URL}?id={company_id}"
        driver.get(company_url)
        self._wait_for_element("id", "EventsYears", "страница компании")

        query = urlencode({"companyId": company_id, "year": api_year})
        api_url = f"{_EVENTS_API_URL}?{query}"
        response = driver.execute_async_script(
            """
            const [url, done] = arguments;
            const target = new URL(url, window.location.origin);
            const token = document.querySelector(
                'input[name="__RequestVerificationToken"]'
            )?.value;
            if (token) target.searchParams.set("__RequestVerificationToken", token);
            fetch(target.toString(), {
                credentials: "same-origin",
                headers: {
                    "Accept": "application/json, text/javascript, */*; q=0.01",
                    "X-Requested-With": "XMLHttpRequest"
                }
            }).then(async response => done({
                status: response.status,
                body: await response.text()
            })).catch(error => done({error: String(error)}));
            """,
            api_url,
        )
        if not isinstance(response, dict) or response.get("error"):
            raise RuntimeError(
                f"Не удалось получить список событий из браузера: "
                f"{response.get('error') if isinstance(response, dict) else response}"
            )
        status = int(response.get("status", 0))
        response_body = str(response.get("body", ""))
        if _is_forbidden_response(status, response_body):
            raise EdisclosureAccessBlockedError(
                status=status,
                response_text=response_body,
                url=api_url,
            )
        raw_events: Any = None
        if 200 <= status < 300:
            try:
                raw_events = json.loads(response_body)
            except (TypeError, json.JSONDecodeError):
                pass

        if not isinstance(raw_events, list):
            # A failed fetch does not display a site challenge in the browser.
            # Navigate to that same URL so any verification is shown in Chrome.
            driver.get(api_url)
            self._raise_if_current_page_is_forbidden(status=status, url=api_url)
            from selenium.webdriver.support.ui import WebDriverWait
            from selenium.common.exceptions import TimeoutException

            try:
                WebDriverWait(driver, _INITIAL_WAIT_SECONDS, poll_frequency=0.5).until(
                    lambda current: self._is_challenge_page()
                    or bool(current.find_element("tag name", "body").text.strip())
                )
            except TimeoutException:
                pass
            if self._is_challenge_page():
                self._show_challenge_message()
                try:
                    WebDriverWait(
                        driver,
                        _CHALLENGE_WAIT_SECONDS,
                        poll_frequency=1,
                    ).until(lambda current: not self._is_challenge_page())
                except TimeoutException as exc:
                    raise RuntimeError(
                        f"Проверка сайта не завершена за {_CHALLENGE_WAIT_SECONDS} секунд."
                    ) from exc
                page_body = driver.find_element("tag name", "body").text
                try:
                    raw_events = json.loads(page_body)
                except json.JSONDecodeError as exc:
                    raise RuntimeError(
                        f"После проверки сайт не вернул список событий за {api_year}."
                    ) from exc
            elif status < 200 or status >= 300:
                raise RuntimeError(
                    f"Сайт вернул HTTP {status} при загрузке списка событий за {api_year}."
                )
            else:
                raise RuntimeError(
                    f"Ответ сайта со списком событий за {api_year} не является JSON."
                )
        if not isinstance(raw_events, list):
            return []

        selected: List[Dict[str, Any]] = []
        for event in raw_events:
            if not isinstance(event, dict):
                continue
            raw_date = event.get("eventDate")
            if not raw_date:
                continue
            try:
                event_date = datetime.fromisoformat(
                    str(raw_date).replace("Z", "+00:00")
                ).date()
            except (ValueError, TypeError):
                continue
            if event_date >= boundary:
                continue
            pseudo_guid = str(event.get("pseudoGUID") or "")
            if pseudo_guid and pseudo_guid not in (skip_pseudo_guids or set()):
                selected.append(event)
        selected.sort(
            key=lambda event: datetime.fromisoformat(
                str(event["eventDate"]).replace("Z", "+00:00")
            ).date(),
            reverse=True,
        )

        total = len(selected)
        texts_by_guid: Dict[str, Optional[str]] = {}
        for offset in range(0, total, _EVENT_PAGE_BATCH_SIZE):
            batch_events = selected[offset : offset + _EVENT_PAGE_BATCH_SIZE]
            pending_guids = [str(event["pseudoGUID"]) for event in batch_events]
            attempts = 0
            while pending_guids and attempts < 3:
                try:
                    batch_result = self._fetch_event_text_batch(pending_guids)
                except EdisclosureAccessBlockedError as exc:
                    texts_by_guid.update(exc.partial_texts)
                    exc.partial_events = self._format_event_payloads(selected, texts_by_guid)
                    raise
                texts_by_guid.update(batch_result["texts"])
                challenge_guid = batch_result.get("challenge_guid")
                if not challenge_guid:
                    break

                try:
                    challenge_text = self._fetch_event_text_visible(challenge_guid)
                except EdisclosureAccessBlockedError as exc:
                    exc.partial_events = self._format_event_payloads(selected, texts_by_guid)
                    raise
                texts_by_guid[challenge_guid] = challenge_text
                pending_guids = [
                    guid
                    for guid in pending_guids
                    if guid != challenge_guid and not texts_by_guid.get(guid)
                ]
                attempts += 1

            if pending_guids and attempts >= 3:
                raise RuntimeError(
                    "Сайт продолжает запрашивать проверку при загрузке страниц событий. "
                    "Выгрузка остановлена; сохранённые ранее годы можно продолжить повторным запуском."
                )

            processed = min(offset + len(batch_events), total)
            if processed == total or processed % 25 == 0:
                print(
                    f"  [BROWSER EVENTS] {api_year}: обработано {processed}/{total}, "
                    f"текст получен у {sum(bool(texts_by_guid.get(guid)) for guid in texts_by_guid)}",
                    flush=True,
                )

        return self._format_event_payloads(selected, texts_by_guid)

    @staticmethod
    def _format_event_payloads(
        selected: List[Dict[str, Any]],
        texts_by_guid: Dict[str, Optional[str]],
    ) -> List[Dict[str, Optional[str]]]:
        results: List[Dict[str, Optional[str]]] = []
        for event in selected:
            guid = str(event["pseudoGUID"])
            text = texts_by_guid.get(guid)
            if text:
                try:
                    event_date = datetime.fromisoformat(
                        str(event.get("eventDate", "")).replace("Z", "+00:00")
                    ).date().isoformat()
                except (ValueError, TypeError):
                    event_date = None
                results.append(
                    {
                        "event_name": str(event.get("eventName") or ""),
                        "event_date": event_date,
                        "full_text": text,
                        "pseudoGUID": guid,
                        "is_corrected_by_another_event": bool(
                            event.get("isCorrectedByAnotherEvent")
                        ),
                        "file_icon_name": str(event["fileIconName"])
                        if event.get("fileIconName")
                        else None,
                    }
                )
        return results

    def _fetch_event_text_batch(
        self,
        pseudo_guids: List[str],
    ) -> Dict[str, Any]:
        """Fetch event pages with low concurrency inside the visible browser."""
        driver = self._require_driver()
        payload = driver.execute_async_script(
            """
            const [guids, minIntervalMs, done] = arguments;
            const results = {};
            const errors = [];
            let next = 0;
            let lastRequestAt = 0;
            let challengeGuid = null;
            let blocked = null;
            const challengeMarkers = [
                "cf-challenge", "cf-turnstile", "challenge-running",
                "checking your browser", "just a moment", "проверка браузера",
                "ddos protection"
            ];
            const delay = ms => new Promise(resolve => setTimeout(resolve, ms));
            async function worker() {
                while (next < guids.length && !challengeGuid && !blocked) {
                    const index = next++;
                    const guid = guids[index];
                    const url = new URL("/portal/event.aspx", window.location.origin);
                    url.searchParams.set("EventId", guid);
                    try {
                        const waitMs = Math.max(0, minIntervalMs - (Date.now() - lastRequestAt));
                        if (waitMs) await delay(waitMs);
                        lastRequestAt = Date.now();
                        const response = await fetch(url.toString(), {
                            credentials: "same-origin",
                            headers: {"Accept": "text/html,application/xhtml+xml,*/*;q=0.8"}
                        });
                        const markup = await response.text();
                        const documentPage = new DOMParser().parseFromString(markup, "text/html");
                        const visibleText = documentPage.body?.innerText || documentPage.body?.textContent || "";
                        const pageText = `${documentPage.title || ""} ${visibleText} ${markup.slice(0, 12000)}`.toLowerCase();
                        const hasChallenge = challengeMarkers.some(marker => pageText.includes(marker));
                        const hasForbidden = /^\\s*#?\\s*forbidden\\b/im.test(visibleText) ||
                            (pageText.includes("forbidden") &&
                             ["datetime:", "ip:", "id:", "origin:"].every(label => pageText.includes(label)));
                        if (hasForbidden || response.status === 429 || (response.status === 403 && !hasChallenge)) {
                            blocked = {
                                status: response.status,
                                body: visibleText || markup,
                                url: url.toString(),
                                guid
                            };
                            break;
                        }
                        if (hasChallenge) {
                            challengeGuid = guid;
                            break;
                        }
                        if (!response.ok) {
                            errors.push(`${guid}: HTTP ${response.status}`);
                            continue;
                        }
                        const root = documentPage.getElementById("cont_wrap");
                        if (!root) {
                            results[guid] = null;
                            continue;
                        }
                        const blocks = [...root.querySelectorAll("div[style]")].filter(el =>
                            /word-break\\s*:\\s*break-word/i.test(el.getAttribute("style") || "")
                        );
                        const target = blocks[1] || blocks[0];
                        const text = target ? (target.innerText || target.textContent || "").trim() : "";
                        results[guid] = text || null;
                    } catch (error) {
                        errors.push(`${guid}: ${String(error)}`);
                    }
                }
            }
            Promise.all(Array.from({length: Math.min(1, guids.length)}, () => worker()))
                .then(() => done({texts: results, challenge_guid: challengeGuid, blocked, errors}));
            """,
            pseudo_guids,
            int(_EVENT_PAGE_MIN_INTERVAL_SECONDS * 1000),
        )
        if not isinstance(payload, dict):
            raise RuntimeError("Браузер вернул некорректный ответ при загрузке страниц событий.")
        blocked = payload.get("blocked")
        if isinstance(blocked, dict):
            texts = payload.get("texts")
            raise EdisclosureAccessBlockedError(
                status=int(blocked.get("status", 403)),
                response_text=str(blocked.get("body", "")),
                url=str(blocked.get("url", "")),
                failed_guid=str(blocked.get("guid", "")) or None,
                partial_texts=texts if isinstance(texts, dict) else {},
            )
        if payload.get("errors"):
            raise RuntimeError(
                "Не удалось загрузить некоторые страницы событий через браузер: "
                + "; ".join(payload["errors"][:3])
            )
        texts = payload.get("texts")
        return {
            "texts": texts if isinstance(texts, dict) else {},
            "challenge_guid": payload.get("challenge_guid"),
        }

    def _fetch_event_text_visible(self, pseudo_guid: str) -> Optional[str]:
        """Open one event in the visible tab, including for manual verification."""
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.common.exceptions import TimeoutException

        driver = self._require_driver()
        driver.get(f"{_EVENT_PAGE_URL}?EventId={pseudo_guid}")

        try:
            WebDriverWait(driver, _INITIAL_WAIT_SECONDS, poll_frequency=0.5).until(
                lambda current: current.find_elements("id", "cont_wrap")
                or self._is_forbidden_page()
                or self._is_challenge_page()
            )
        except TimeoutException:
            return None

        self._raise_if_current_page_is_forbidden(
            url=f"{_EVENT_PAGE_URL}?EventId={pseudo_guid}"
        )
        if not driver.find_elements("id", "cont_wrap"):
            self._wait_for_element("id", "cont_wrap", "текст события")

        text = driver.execute_script(
            """
            const root = document.getElementById("cont_wrap");
            if (!root) return null;
            const blocks = [...root.querySelectorAll("div[style]")].filter(el =>
                /word-break\\s*:\\s*break-word/i.test(el.getAttribute("style") || "")
            );
            const target = blocks[1] || blocks[0];
            return target ? (target.innerText || target.textContent || "").trim() : null;
            """
        )
        return text.strip() if isinstance(text, str) and text.strip() else None

    # ------------------------------------------------------------------
    # Emission documents support
    # ------------------------------------------------------------------

    def search_companies_by_inn(self, inn: str) -> List[Dict[str, Any]]:
        """Ищет компании по ИНН через браузер, обходя антибот-проверку."""
        driver = self._require_driver()
        self._ensure_search_page()

        def _build_form() -> str:
            token = driver.execute_script(
                "return document.querySelector('input[name=\"__RequestVerificationToken\"]')"
                "?.value || '';"
            )
            return urlencode(
                {
                    "textfield": inn,
                    "radReg": "FederalDistricts",
                    "districtsCheckboxGroup": "-1",
                    "regionsCheckboxGroup": "-1",
                    "branchesCheckboxGroup": "-1",
                    "lastPageSize": "10",
                    "lastPageNumber": "1",
                    "query": inn,
                    "__RequestVerificationToken": token or "",
                }
            )

        result = self._request_via_page(
            _SEARCH_API_URL,
            method="POST",
            body_builder=_build_form,
            content_type="application/x-www-form-urlencoded; charset=UTF-8",
            description=f"поиск компании по ИНН {inn}",
        )
        try:
            payload = json.loads(str(result.get("body") or ""))
        except (TypeError, json.JSONDecodeError) as exc:
            raise RuntimeError(
                "Браузер получил не JSON при поиске компании по ИНН "
                f"{inn} (HTTP {result.get('status')})."
            ) from exc

        found_list = payload.get("foundCompaniesList") or []
        companies: List[Dict[str, Any]] = []
        for item in found_list:
            if not isinstance(item, dict):
                continue
            companies.append(
                {
                    "id": item.get("id"),
                    "name": item.get("name"),
                    "district": item.get("district"),
                    "region": item.get("region"),
                    "branch": item.get("branch"),
                }
            )
        return companies

    def fetch_emission_documents_html(self, company_id: int) -> str:
        """Открывает страницу эмиссионных документов и ждёт проверку сайта."""
        driver = self._require_driver()
        url = f"{_FILES_PAGE_URL}?id={company_id}&type=7"
        print(f"  [BROWSER] GET {url}", flush=True)
        driver.get(url)
        self._wait_for_element("id", "cont_wrap", "страница эмиссионных документов")
        self._raise_if_current_page_is_forbidden(url=driver.current_url)
        return driver.page_source

    def download_file(
        self,
        file_url: str,
        referer: Optional[str] = None,
    ) -> Tuple[Optional[bytes], Optional[str]]:
        """Скачивает файл через fetch внутри открытого браузера."""
        resolved = (file_url or "").strip()
        if resolved and not resolved.startswith(("http://", "https://")):
            resolved = urljoin(_MAIN_PAGE_URL + "/", resolved.lstrip("/"))
        if not resolved:
            return None, None

        self._ensure_page_origin()
        print(
            f"  [BROWSER FILE] GET {resolved} (referer: {referer or '-'})",
            flush=True,
        )
        result = self._request_via_page(
            resolved,
            binary=True,
            description=f"файл эмиссионного документа {resolved}",
        )
        status = int(result.get("status") or 0)
        if status < 200 or status >= 300:
            print(
                f"  [BROWSER FILE] HTTP {status} при скачивании {resolved}",
                flush=True,
            )
            return None, None

        raw_body = str(result.get("body") or "")
        try:
            content = base64.b64decode(raw_body)
        except (binascii.Error, ValueError) as exc:
            raise RuntimeError(
                f"Браузер вернул некорректные данные файла {resolved}."
            ) from exc

        content_type = str(result.get("contentType") or "")
        if "text/html" in content_type.lower():
            preview = content[:4096].decode("utf-8", errors="ignore")
            protection = _detect_protection(preview)
            if protection:
                print(
                    f"  [BROWSER FILE] WARNING: вместо файла получена "
                    f"антибот-страница e-disclosure (маркер={protection!r}); "
                    f"url={resolved}",
                    flush=True,
                )
                return None, None
            print(
                f"  [BROWSER FILE] WARNING: вместо файла получен HTML "
                f"(content-type={content_type!r}, bytes={len(content)}); "
                f"url={resolved}",
                flush=True,
            )

        from conversion_service.app.utils.edisclosure_utils import (
            extract_filename_from_content_disposition,
        )
        filename = extract_filename_from_content_disposition(
            str(result.get("disposition") or "")
        )
        return content, filename

    def _ensure_page_origin(self) -> None:
        """Гарантирует, что текущая страница принадлежит e-disclosure.ru."""
        driver = self._require_driver()
        try:
            current_url = driver.current_url or ""
        except Exception:
            current_url = ""
        if "e-disclosure.ru" not in current_url:
            driver.get(_SEARCH_PAGE_URL)
            self._wait_for_element("id", "textfield", "поле поиска компании")
            return
        self._raise_if_current_page_is_forbidden(url=current_url)
        if self._is_challenge_page():
            self._show_challenge_message()
            self._wait_after_challenge(
                lambda current: not self._is_challenge_page(),
                "завершение проверки сайта",
            )

    def _ensure_search_page(self) -> None:
        """Открывает страницу поиска, если браузер ещё не на ней."""
        driver = self._require_driver()
        try:
            current_url = driver.current_url or ""
        except Exception:
            current_url = ""
        if not current_url.startswith(_SEARCH_PAGE_URL):
            driver.get(_SEARCH_PAGE_URL)
            self._wait_for_element("id", "textfield", "поле поиска компании")
            return
        self._raise_if_current_page_is_forbidden(url=current_url)
        if self._is_challenge_page():
            self._show_challenge_message()
            self._wait_after_challenge(
                lambda current: not self._is_challenge_page(),
                "завершение проверки сайта",
            )

    def _recover_after_challenge(self) -> None:
        """Перезагружает страницу поиска для прохождения проверки вручную."""
        driver = self._require_driver()
        driver.get(_SEARCH_PAGE_URL)
        self._wait_for_element("id", "textfield", "поле поиска компании")

    def _request_via_page(
        self,
        url: str,
        *,
        method: str = "GET",
        body: Optional[str] = None,
        body_builder: Optional[Callable[[], str]] = None,
        content_type: Optional[str] = None,
        binary: bool = False,
        description: str = "данные e-disclosure",
    ) -> Dict[str, Any]:
        """Выполняет same-origin fetch из открытой страницы браузера."""
        driver = self._require_driver()
        last_result: Optional[Dict[str, Any]] = None
        for attempt in range(2):
            request_body = body_builder() if body_builder is not None else (body or "")
            result = driver.execute_async_script(
                _PAGE_FETCH_JS,
                url,
                method,
                request_body,
                content_type or "",
                bool(binary),
            )
            if not isinstance(result, dict) or result.get("error"):
                detail = result.get("error") if isinstance(result, dict) else result
                raise RuntimeError(
                    f"Не удалось выполнить запрос через браузер ({description}): {detail}"
                )
            last_result = result
            status = int(result.get("status") or 0)
            response_content_type = str(result.get("contentType") or "")
            preview = self._result_preview(result, binary=binary)
            if _is_forbidden_response(status, preview):
                raise EdisclosureAccessBlockedError(
                    status=status,
                    response_text=preview,
                    url=url,
                )
            if self._is_challenge_result(status, response_content_type, preview):
                if attempt == 0:
                    self._show_challenge_message()
                    self._recover_after_challenge()
                    continue
                raise RuntimeError(
                    f"Проверка сайта не завершена; запрос {url} не выполнен."
                )
            return result
        return last_result or {}

    @staticmethod
    def _result_preview(result: Dict[str, Any], *, binary: bool) -> str:
        """Возвращает текстовый превью ответа для детекта антибот-страницы."""
        raw = str(result.get("body") or "")
        if not binary:
            return raw[:8000]
        chunk = raw[:16000]
        chunk = chunk[: len(chunk) - (len(chunk) % 4)]
        try:
            return base64.b64decode(chunk).decode("utf-8", errors="ignore")
        except (binascii.Error, ValueError):
            return ""

    @staticmethod
    def _is_challenge_result(status: int, content_type: str, preview: str) -> bool:
        """Определяет, что ответ сайта является страницей проверки браузера."""
        if status == 429:
            return False
        if status == 403:
            return True
        if _detect_protection(preview):
            return True
        lowered = (preview or "").lower()
        return any(marker in lowered for marker in _CHALLENGE_MARKERS)

    def _wait_for_element(self, by: str, selector: str, description: str) -> Any:
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.common.exceptions import TimeoutException

        driver = self._require_driver()
        self._raise_if_current_page_is_forbidden(url=driver.current_url)
        condition = lambda current: current.find_element(by, selector)
        if self._is_challenge_page():
            self._show_challenge_message()
            return self._wait_after_challenge(condition, description)
        try:
            return WebDriverWait(driver, _INITIAL_WAIT_SECONDS, poll_frequency=0.5).until(
                condition
            )
        except TimeoutException:
            self._raise_if_current_page_is_forbidden(url=driver.current_url)
            if not self._is_challenge_page():
                raise RuntimeError(
                    f"Не удалось найти {description} (селектор {selector!r}); "
                    f"открыта страница {driver.current_url}."
                )
            self._show_challenge_message()
            return self._wait_after_challenge(condition, description)

    def _wait_for_elements(self, by: str, selector: str, description: str) -> List[Any]:
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.common.exceptions import TimeoutException

        driver = self._require_driver()
        self._raise_if_current_page_is_forbidden(url=driver.current_url)
        condition = lambda current: current.find_elements(by, selector) or False
        if self._is_challenge_page():
            self._show_challenge_message()
            return self._wait_after_challenge(condition, description)
        try:
            return WebDriverWait(driver, _INITIAL_WAIT_SECONDS, poll_frequency=0.5).until(
                condition
            )
        except TimeoutException:
            self._raise_if_current_page_is_forbidden(url=driver.current_url)
            if not self._is_challenge_page():
                raise RuntimeError(
                    f"Не удалось найти {description} (селектор {selector!r}); "
                    f"открыта страница {driver.current_url}."
                )
            self._show_challenge_message()
            return self._wait_after_challenge(condition, description)

    def _wait_after_challenge(self, condition: Any, description: str) -> Any:
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.common.exceptions import TimeoutException

        try:
            return WebDriverWait(
                self._require_driver(),
                _CHALLENGE_WAIT_SECONDS,
                poll_frequency=1,
            ).until(condition)
        except TimeoutException as exc:
            raise RuntimeError(
                f"Проверка сайта не завершена за {_CHALLENGE_WAIT_SECONDS} секунд "
                f"при ожидании: {description}."
            ) from exc

    def _is_challenge_page(self) -> bool:
        driver = self._require_driver()
        try:
            current_url = driver.current_url.lower()
            if any(marker in current_url for marker in _CHALLENGE_URL_MARKERS):
                return True
            page_content = f"{driver.title}\n{driver.page_source}".lower()
        except Exception:
            return False
        if _detect_protection(page_content):
            return True
        return any(marker in page_content for marker in _CHALLENGE_MARKERS)

    def _is_forbidden_page(self) -> bool:
        driver = self._require_driver()
        try:
            page_text = driver.execute_script(
                "return document.body?.innerText || document.body?.textContent || document.title || '';"
            )
        except Exception:
            try:
                page_text = driver.page_source
            except Exception:
                return False
        return _is_forbidden_response(None, str(page_text or ""))

    def _raise_if_current_page_is_forbidden(
        self,
        *,
        status: Optional[int] = None,
        url: Optional[str] = None,
    ) -> None:
        driver = self._require_driver()
        try:
            page_text = driver.execute_script(
                "return document.body?.innerText || document.body?.textContent || document.title || '';"
            )
        except Exception:
            try:
                page_text = driver.page_source
            except Exception:
                page_text = ""
        if _is_forbidden_response(status, str(page_text or "")):
            raise EdisclosureAccessBlockedError(
                status=status,
                response_text=str(page_text or ""),
                url=url or driver.current_url,
            )

    @staticmethod
    def _show_challenge_message() -> None:
        print(
            "  [BROWSER] Сайт запросил проверку. Пройдите её в открытом окне Chrome; "
            "выгрузка продолжится автоматически.",
            flush=True,
        )

    def _require_driver(self) -> Any:
        if self._driver is None:
            raise RuntimeError("Браузерная сессия не запущена.")
        return self._driver


class LazyEdisclosureBrowser:
    """Запускает видимый браузер только при первом обращении и держит его открытым."""

    def __init__(self) -> None:
        self._stack: ExitStack = ExitStack()
        self._session: Optional[EdisclosureBrowserSession] = None
        self._startup_error: Optional[Exception] = None

    def __enter__(self) -> "LazyEdisclosureBrowser":
        return self

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        self._stack.__exit__(exc_type, exc, traceback)

    @property
    def started(self) -> bool:
        return self._session is not None

    def get(self) -> EdisclosureBrowserSession:
        if self._startup_error is not None:
            raise RuntimeError(
                f"Браузерная сессия недоступна: {self._startup_error}"
            ) from self._startup_error
        if self._session is None:
            try:
                self._session = self._stack.enter_context(EdisclosureBrowserSession())
            except Exception as exc:
                self._startup_error = exc
                raise
        return self._session

