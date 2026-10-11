"""FastAPI web-form for manual cookie entry from browser DevTools.

Provides a browser-based UI where the user can paste cookies copied from
Chrome DevTools (Application → Cookies tab or Network → Copy as cURL)
and have them parsed and saved to ``cookies_data.json``.

This module is a fallback mechanism for when the automated DrissionPage
Cloudflare bypass fails.

Usage as a standalone server::

    uvicorn app.utils.edisclosure.cookie_web_form:app --host 127.0.0.1 --port 5000

Or include the router in the main FastAPI app for integrated access.
"""

import json
import re
import time
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, APIRouter
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel

# ---------------------------------------------------------------------------
# HTML template for the cookie parser UI
# ---------------------------------------------------------------------------
HTML_TEMPLATE: str = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Парсер cookies e-disclosure</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: #f0f2f5; padding: 20px; }
        .container { max-width: 1000px; margin: 0 auto; background: white; border-radius: 12px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); padding: 30px; }
        h1 { color: #1a73e8; margin-bottom: 20px; font-size: 24px; }
        .tabs { display: flex; gap: 5px; margin-bottom: 15px; border-bottom: 2px solid #dadce0; }
        .tab { padding: 10px 20px; cursor: pointer; border: none; background: none; font-size: 14px; font-weight: 500; color: #5f6368; border-bottom: 3px solid transparent; transition: all 0.2s; }
        .tab.active { color: #1a73e8; border-bottom-color: #1a73e8; }
        .tab:hover { background: #f8f9fa; }
        .tab-content { display: none; }
        .tab-content.active { display: block; }
        .instructions { background: #e8f0fe; border-left: 4px solid #1a73e8; padding: 15px 20px; border-radius: 4px; margin-bottom: 20px; }
        .instructions ol { margin-left: 20px; line-height: 1.8; }
        textarea { width: 100%; padding: 12px; font-family: 'Consolas', monospace; font-size: 13px; border: 1px solid #dadce0; border-radius: 8px; resize: vertical; }
        textarea:focus { outline: none; border-color: #1a73e8; box-shadow: 0 0 0 3px rgba(26,115,232,0.2); }
        .textarea-tab { height: 350px; }
        .textarea-headers { height: 400px; }
        .buttons { display: flex; gap: 10px; margin-top: 15px; flex-wrap: wrap; }
        button { padding: 10px 30px; border: none; border-radius: 6px; font-size: 16px; cursor: pointer; transition: all 0.2s; }
        .btn-parse { background: #1a73e8; color: white; }
        .btn-parse:hover { background: #1557b0; }
        .btn-clear { background: #dadce0; color: #333; }
        .btn-clear:hover { background: #c5c7ca; }
        .result { margin-top: 20px; padding: 15px; border-radius: 8px; display: none; }
        .result.success { display: block; background: #e6f4ea; border: 1px solid #34a853; }
        .result.error { display: block; background: #fce8e6; border: 1px solid #ea4335; }
        .result pre { background: #f8f9fa; padding: 10px; border-radius: 4px; overflow-x: auto; font-size: 12px; margin-top: 10px; max-height: 300px; overflow-y: auto; }
        .cookie-list { background: #f8f9fa; padding: 10px 15px; border-radius: 6px; margin-top: 10px; max-height: 200px; overflow-y: auto; }
        .cookie-list .badge { display: inline-block; background: #1a73e8; color: white; border-radius: 12px; padding: 2px 10px; font-size: 12px; margin-right: 5px; }
        .stats { display: flex; gap: 20px; margin-top: 10px; flex-wrap: wrap; }
        .stat { background: #f8f9fa; padding: 8px 16px; border-radius: 6px; font-size: 14px; }
        .stat strong { color: #1a73e8; }
        .footer { margin-top: 20px; color: #5f6368; font-size: 13px; border-top: 1px solid #dadce0; padding-top: 15px; }
        .token-input { margin-top: 10px; display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }
        .token-input input { flex: 1; min-width: 200px; padding: 8px 12px; border: 1px solid #dadce0; border-radius: 6px; font-family: monospace; font-size: 13px; }
        .token-input input:focus { outline: none; border-color: #1a73e8; }
        .token-input label { font-weight: 500; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🍪 Парсер cookies e-disclosure</h1>
        
        <div class="tabs">
            <button class="tab active" onclick="switchTab('tab-cookies')">📋 Таблица Cookies</button>
            <button class="tab" onclick="switchTab('tab-headers')">📨 Заголовки (cURL)</button>
        </div>
        
        <!-- Tab: Cookie table -->
        <div id="tab-cookies" class="tab-content active">
            <div class="instructions">
                <strong>📋 Инструкция:</strong>
                <ol>
                    <li>Откройте <strong>F12 → Application → Cookies</strong> на странице компании</li>
                    <li>Выделите все строки таблицы (<strong>Ctrl+A</strong>)</li>
                    <li>Скопируйте (<strong>Ctrl+C</strong>) и вставьте в поле ниже</li>
                    <li>Нажмите <strong>"Парсить"</strong></li>
                </ol>
            </div>
            <textarea id="cookiesInput" class="textarea-tab" placeholder="Вставьте скопированную таблицу cookies..."></textarea>
            <div class="token-input">
                <label>🔑 Токен (если не найден):</label>
                <input id="tokenInput" placeholder="Вставьте __RequestVerificationToken вручную" />
            </div>
            <div class="buttons">
                <button class="btn-parse" onclick="parseCookies()">🔍 Парсить</button>
                <button class="btn-clear" onclick="clearText('cookiesInput')">🗑️ Очистить</button>
            </div>
        </div>
        
        <!-- Tab: Headers (cURL) -->
        <div id="tab-headers" class="tab-content">
            <div class="instructions">
                <strong>📋 Инструкция:</strong>
                <ol>
                    <li>Откройте <strong>F12 → Network</strong> на странице компании</li>
                    <li>Найдите запрос к <strong>/api/events/page</strong></li>
                    <li>Правой кнопкой → <strong>Copy → Copy as cURL</strong></li>
                    <li>Вставьте в поле ниже и нажмите <strong>"Парсить"</strong></li>
                </ol>
            </div>
            <textarea id="headersInput" class="textarea-headers" placeholder="Вставьте скопированные заголовки..."></textarea>
            <div class="buttons">
                <button class="btn-parse" onclick="parseHeaders()">🔍 Парсить</button>
                <button class="btn-clear" onclick="clearText('headersInput')">🗑️ Очистить</button>
            </div>
        </div>
        
        <div id="result" class="result"></div>
        
        <div class="footer">
            Файл <strong>cookies_data.json</strong> будет сохранён в папке со скриптом.
        </div>
    </div>
    
    <script>
        function switchTab(tabId) {
            document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
            document.querySelectorAll('.tab').forEach(el => el.classList.remove('active'));
            document.getElementById(tabId).classList.add('active');
            document.querySelector(`.tab[onclick="switchTab('${tabId}')"]`).classList.add('active');
        }
        
        function clearText(id) {
            document.getElementById(id).value = '';
            document.getElementById('result').className = 'result';
            document.getElementById('result').innerHTML = '';
        }
        
        async function parseCookies() {
            const text = document.getElementById('cookiesInput').value;
            const token = document.getElementById('tokenInput').value.trim();
            const resultDiv = document.getElementById('result');
            
            if (!text.trim()) {
                resultDiv.className = 'result error';
                resultDiv.innerHTML = '❌ Пожалуйста, вставьте данные.';
                return;
            }
            
            try {
                const response = await fetch('/edisclosure-cookies/parse-cookies', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ text: text, token: token })
                });
                
                const data = await response.json();
                showResult(resultDiv, data);
            } catch (error) {
                resultDiv.className = 'result error';
                resultDiv.innerHTML = '❌ Ошибка: ' + error;
            }
        }
        
        async function parseHeaders() {
            const text = document.getElementById('headersInput').value;
            const resultDiv = document.getElementById('result');
            
            if (!text.trim()) {
                resultDiv.className = 'result error';
                resultDiv.innerHTML = '❌ Пожалуйста, вставьте данные.';
                return;
            }
            
            try {
                const response = await fetch('/edisclosure-cookies/parse-headers', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ text: text })
                });
                
                const data = await response.json();
                showResult(resultDiv, data);
            } catch (error) {
                resultDiv.className = 'result error';
                resultDiv.innerHTML = '❌ Ошибка: ' + error;
            }
        }
        
        function showResult(resultDiv, data) {
            if (data.error) {
                resultDiv.className = 'result error';
                resultDiv.innerHTML = '❌ ' + data.error;
                return;
            }
            
            let html = '<div class="result success">';
            html += '<h3>✅ Готово!</h3>';
            html += '<div class="stats">';
            html += '<div class="stat">🍪 <strong>' + data.cookie_count + '</strong> cookies</div>';
            html += '<div class="stat">🔑 ' + (data.token ? '✅ Токен найден' : '❌ Токен не найден') + '</div>';
            html += '<div class="stat">🏢 Company ID: <strong>' + (data.company_id || 'N/A') + '</strong></div>';
            html += '</div>';
            
            if (data.cookies && Object.keys(data.cookies).length > 0) {
                html += '<div class="cookie-list">';
                html += '<strong>🍪 Cookies:</strong><br>';
                for (let name in data.cookies) {
                    const value = data.cookies[name];
                    const display = value.length > 50 ? value.substring(0, 50) + '...' : value;
                    html += '<span class="badge">' + name + '</span> ' + display + '<br>';
                }
                html += '</div>';
            }
            
            html += '<p style="margin-top:10px;">📁 Файл сохранён: <strong>cookies_data.json</strong></p>';
            html += '<pre>' + JSON.stringify(data.output, null, 2) + '</pre>';
            html += '</div>';
            
            resultDiv.className = 'result success';
            resultDiv.innerHTML = html;
        }
    </script>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class ParseRequest(BaseModel):
    """Request body for cookie/header parsing endpoints."""

    text: str
    token: str = ""


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------

def _parse_cookie_tab_line(line: str) -> Optional[dict]:
    """Parse a single tab-separated cookie row."""
    parts = line.split("\t")
    if len(parts) < 2:
        return None
    name = parts[0].strip()
    value = parts[1].strip()
    if not name or not value:
        return None
    if name.startswith("_"):
        return None
    return {name: value}


def parse_cookies_from_tab(text: str) -> dict:
    """Parse a cookies table copied with tab-separated values."""
    cookies: dict = {}
    for line in text.split("\n"):
        line = line.strip()
        if not line:
            continue
        # Skip header rows
        if "Название" in line or "Значение" in line or "Домен" in line:
            continue
        parsed = _parse_cookie_tab_line(line)
        if parsed:
            cookies.update(parsed)
    return cookies


def parse_cookie_string(cookie_str: str) -> dict:
    """Parse a ``Cookie:`` header value into a dict."""
    cookies: dict = {}
    for item in cookie_str.split(";"):
        item = item.strip()
        if "=" in item:
            name, value = item.split("=", 1)
            name = name.strip()
            value = value.strip()
            if name:
                cookies[name] = value
    return cookies


def parse_headers_from_text(text: str) -> dict:
    """Parse headers text (e.g. from Copy as cURL) to extract cookies."""
    cookies: dict = {}
    referer: str = ""
    company_id: Optional[str] = None
    cookie_str: Optional[str] = None

    for line in text.split("\n"):
        line = line.strip()
        if not line:
            continue

        if line.lower().startswith("cookie:"):
            cookie_str = line[7:].strip()
        elif line.lower().startswith("cookie "):
            cookie_str = line[6:].strip()
        elif "cookie" in line.lower() and "=" in line and ";" in line:
            if not cookie_str:
                cookie_str = line

        if line.lower().startswith("referer:"):
            referer = line[8:].strip()
            match = re.search(r"id=(\d+)", referer)
            if match:
                company_id = match.group(1)
        elif line.lower().startswith("referer "):
            referer = line[7:].strip()
            match = re.search(r"id=(\d+)", referer)
            if match:
                company_id = match.group(1)

    if cookie_str:
        cookies = parse_cookie_string(cookie_str)

    return {"cookies": cookies, "referer": referer, "company_id": company_id}


# ---------------------------------------------------------------------------
# Save cookies to file (uses CookieManager)
# ---------------------------------------------------------------------------

def _save_parsed_cookies(
    cookies: dict,
    token: str,
    referer: str = "",
    company_id: Optional[str] = None,
) -> dict:
    """Save parsed cookies via the CookieManager and return output."""
    from app.utils.edisclosure.cookie_manager import get_cookie_manager

    manager = get_cookie_manager()
    manager.save_cookies(
        cookies,
        token,
        extra={
            "referer": referer,
            "user_agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/148.0.0.0 YaBrowser/26.6.0.0 Safari/537.36"
            ),
            "company_id": company_id,
        },
    )
    # Also invalidate the cache to force re-read
    manager.invalidate()

    return {
        "cookies": cookies,
        "token": token,
        "timestamp": time.time(),
        "datetime": time.strftime("%Y-%m-%d %H:%M:%S"),
        "referer": referer,
        "user_agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/148.0.0.0 YaBrowser/26.6.0.0 Safari/537.36"
        ),
        "company_id": company_id,
    }


# ---------------------------------------------------------------------------
# FastAPI router (can be included into the main app)
# ---------------------------------------------------------------------------

cookie_router = APIRouter(prefix="/edisclosure-cookies", tags=["edisclosure-cookies"])


@cookie_router.get("/", response_class=HTMLResponse)
async def cookie_form_page() -> HTMLResponse:
    """Serve the cookie parser web form."""
    return HTMLResponse(content=HTML_TEMPLATE)


@cookie_router.post("/parse-cookies")
async def parse_cookies_endpoint(request: ParseRequest) -> JSONResponse:
    """Parse cookies from a tab-separated table."""
    text = request.text
    manual_token = request.token.strip()

    if not text.strip():
        return JSONResponse({"error": "Пустой ввод"})

    cookies = parse_cookies_from_tab(text)
    if not cookies:
        return JSONResponse(
            {"error": "Не найдены cookies. Проверьте формат данных."}
        )

    # Look for token in cookies
    token = cookies.get("__RequestVerificationToken", "")
    if manual_token and not token:
        token = manual_token

    # Try to find referer/company_id
    referer = ""
    company_id: Optional[str] = None
    for line in text.split("\n"):
        if "referer" in line.lower():
            match = re.search(r"id=(\d+)", line)
            if match:
                company_id = match.group(1)
                referer = (
                    f"https://www.e-disclosure.ru/portal/company.aspx?id={company_id}"
                )
                break

    output = _save_parsed_cookies(cookies, token, referer, company_id)

    return JSONResponse(
        {
            "success": True,
            "cookie_count": len(cookies),
            "token": token,
            "company_id": company_id,
            "cookies": cookies,
            "output": output,
        }
    )


@cookie_router.post("/parse-headers")
async def parse_headers_endpoint(request: ParseRequest) -> JSONResponse:
    """Parse cookies from cURL-style headers."""
    text = request.text
    if not text.strip():
        return JSONResponse({"error": "Пустой ввод"})

    parsed = parse_headers_from_text(text)
    cookies = parsed["cookies"]
    if not cookies:
        return JSONResponse(
            {
                "error": "Не найдены cookies. Проверьте, что вставили "
                "данные с cookie строкой."
            }
        )

    token = cookies.get("__RequestVerificationToken", "")
    referer = parsed.get("referer", "")
    company_id = parsed.get("company_id")

    output = _save_parsed_cookies(cookies, token, referer, company_id)

    return JSONResponse(
        {
            "success": True,
            "cookie_count": len(cookies),
            "token": token,
            "company_id": company_id,
            "cookies": cookies,
            "output": output,
        }
    )


# ---------------------------------------------------------------------------
# Standalone app (for running independently)
# ---------------------------------------------------------------------------

app = FastAPI(title="E-Disclosure Cookie Parser")
app.include_router(cookie_router)

if __name__ == "__main__":
    import uvicorn

    print("=" * 60)
    print("🍪 Парсер cookies e-disclosure - FastAPI")
    print("=" * 60)
    print("\n🌐 Запуск сервера...")
    print("📋 Откройте в браузере: http://localhost:5000/edisclosure-cookies/")
    print("\n📌 Поддерживаются два формата:")
    print("   1. Таблица cookies (копировать из Application → Cookies)")
    print("   2. Заголовки (Copy as cURL из Network)")
    print("\n⚠️  Для остановки нажмите Ctrl+C")
    print("=" * 60)

    uvicorn.run(app, host="127.0.0.1", port=5000)
