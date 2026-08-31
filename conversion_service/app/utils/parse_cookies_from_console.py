"""
Веб-форма для парсинга заголовков из браузера на FastAPI.
Поддерживает:
1. Формат с табуляциями (копирование из вкладки Cookies)
2. Формат с заголовками (Copy as cURL)
Запустите: uvicorn cookie_parser_fastapi:app --host 127.0.0.1 --port 5000 --reload
"""

import json
import re
import time
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel

app = FastAPI()

# HTML шаблон
HTML_TEMPLATE = """
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
        
        <!-- Вкладка: Таблица Cookies -->
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
                <button class="btn-clear" onclick="loadExampleCookies()">📋 Пример</button>
            </div>
        </div>
        
        <!-- Вкладка: Заголовки -->
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
                <button class="btn-clear" onclick="loadExampleHeaders()">📋 Пример</button>
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
                const response = await fetch('/parse-cookies', {
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
                const response = await fetch('/parse-headers', {
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
        
        function loadExampleCookies() {
            document.getElementById('cookiesInput').value = `AspNetCore.Antiforgery.tl_-DOxheG0	CfDJ8OfQNSGQ5XNPn6y_jRQ8QLClr1v1fp6mZkO90RiqIzaL2xD9oWzphko5yF6y0NS8Y-OW5Gol4n6HSi__ansjiu-jzpu1iLFr-vrKnmrcxcWX_MjFs1ShdW70QqC2htwKlIScIS6ZeqrTaMWH0D2GS6I	www.e-disclosure.ru	/	Session	190	✓		Strict
adtech_uid	47e832a6-3e62-493c-b478-c9211ee29e77%3Ae-disclosure.ru	.e-disclosure.ru	/	2027-05-25T16:44:17.000Z	64		✓
spid	1747121721492_2d1cc4e4dc62884b610d62e73a9a0bab_cpd3auh7gj88use7	www.e-disclosure.ru	/	2027-04-14T16:23:50.914Z	67		✓	None
spsc	1785663497792_4d77a032f7f6b169a07f189b917be7f3_4ZGvBWVDGbQwhHaCBNwVUV.VjRU70gO.zxQmVAJqajgZ	.e-disclosure.ru	/	2027-09-06T09:38:29.027Z	95		✓	None
top100_id	t1.2928424.1620947990.1779727204321	.e-disclosure.ru	/	2027-05-25T16:44:17.895Z	44`;
            document.getElementById('tokenInput').value = '';
        }
        
        function loadExampleHeaders() {
            document.getElementById('headersInput').value = `accept: */*
accept-encoding: gzip, deflate, br, zstd
accept-language: ru,en;q=0.9
connection: keep-alive
cookie: spid=1747121721492_2d1cc4e4dc62884b610d62e73a9a0bab_cpd3auh7gj88use7; adtech_uid=47e832a6-3e62-493c-b478-c9211ee29e77%3Ae-disclosure.ru; top100_id=t1.2928424.1620947990.1779727204321; .AspNetCore.Antiforgery.tl_-DOxheG0=CfDJ8OfQNSGQ5XNPn6y_jRQ8QLClr1v1fp6mZkO90RiqIzaL2xD9oWzphko5yF6y0NS8Y-OW5Gol4n6HSi__ansjiu-jzpu1iLFr-vrKnmrcxcWX_MjFs1ShdW70QqC2htwKlIScIS6ZeqrTaMWH0D2GS6I
host: www.e-disclosure.ru
referer: https://www.e-disclosure.ru/portal/company.aspx?id=3043
user-agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 YaBrowser/26.6.0.0 Safari/537.36
x-requested-with: XMLHttpRequest`;
        }
    </script>
</body>
</html>
"""


class ParseRequest(BaseModel):
    text: str
    token: str = ""


def parse_cookie_tab_line(line: str) -> dict:
    """Парсит строку с табуляциями."""
    parts = line.split('\t')
    if len(parts) < 2:
        return None

    name = parts[0].strip()
    value = parts[1].strip()

    if not name or not value:
        return None
    if name.startswith('_'):
        return None

    return {name: value}


def parse_cookies_from_tab(text: str) -> dict:
    """Парсит таблицу cookies с табуляциями."""
    cookies = {}

    for line in text.split('\n'):
        line = line.strip()
        if not line:
            continue

        # Пропускаем заголовки
        if 'Название' in line or 'Значение' in line or 'Домен' in line:
            continue

        parsed = parse_cookie_tab_line(line)
        if parsed:
            cookies.update(parsed)

    return cookies


def parse_cookie_string(cookie_str: str) -> dict:
    """Парсит строку cookie (из заголовков)."""
    cookies = {}
    for item in cookie_str.split(';'):
        item = item.strip()
        if '=' in item:
            name, value = item.split('=', 1)
            name = name.strip()
            value = value.strip()
            if name:
                cookies[name] = value
    return cookies


def parse_headers_from_text(text: str) -> dict:
    """Парсит заголовки из текста."""
    cookies = {}
    referer = ""
    company_id = None

    lines = text.split('\n')
    cookie_str = None

    for line in lines:
        line = line.strip()
        if not line:
            continue

        if line.lower().startswith('cookie:'):
            cookie_str = line[7:].strip()
        elif line.lower().startswith('cookie '):
            cookie_str = line[6:].strip()
        elif 'cookie' in line.lower() and '=' in line and ';' in line:
            if not cookie_str:
                cookie_str = line

        if line.lower().startswith('referer:'):
            referer = line[8:].strip()
            match = re.search(r'id=(\d+)', referer)
            if match:
                company_id = match.group(1)
        elif line.lower().startswith('referer '):
            referer = line[7:].strip()
            match = re.search(r'id=(\d+)', referer)
            if match:
                company_id = match.group(1)

    if cookie_str:
        cookies = parse_cookie_string(cookie_str)

    return {"cookies": cookies, "referer": referer, "company_id": company_id}


@app.get("/", response_class=HTMLResponse)
async def index():
    return HTML_TEMPLATE


@app.post("/parse-cookies")
async def parse_cookies(request: ParseRequest):
    text = request.text
    manual_token = request.token.strip()

    if not text.strip():
        return JSONResponse({"error": "Пустой ввод"})

    cookies = parse_cookies_from_tab(text)

    if not cookies:
        return JSONResponse({
            "error": "Не найдены cookies. Проверьте формат данных."
        })

    # Ищем токен в куках
    token = cookies.get("__RequestVerificationToken", "")

    # Если токен передан вручную
    if manual_token and not token:
        token = manual_token

    # Ищем referer
    referer = ""
    company_id = None

    # Если есть кука с referer, пробуем извлечь
    for line in text.split('\n'):
        if 'referer' in line.lower():
            match = re.search(r'id=(\d+)', line)
            if match:
                company_id = match.group(1)
                referer = f"https://www.e-disclosure.ru/portal/company.aspx?id={company_id}"
                break

    output = {
        "cookies": cookies,
        "token": token,
        "timestamp": time.time(),
        "datetime": time.strftime("%Y-%m-%d %H:%M:%S"),
        "referer": referer,
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 YaBrowser/26.6.0.0 Safari/537.36",
        "company_id": company_id
    }

    # Сохраняем файл
    script_dir = Path(__file__).parent.absolute()
    cookies_file = script_dir / "cookies_data.json"

    with open(cookies_file, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    return JSONResponse({
        "success": True,
        "cookie_count": len(cookies),
        "token": token,
        "company_id": company_id,
        "cookies": cookies,
        "output": output,
        "file_path": str(cookies_file)
    })


@app.post("/parse-headers")
async def parse_headers(request: ParseRequest):
    text = request.text

    if not text.strip():
        return JSONResponse({"error": "Пустой ввод"})

    parsed = parse_headers_from_text(text)
    cookies = parsed["cookies"]

    if not cookies:
        return JSONResponse({
            "error": "Не найдены cookies. Проверьте, что вставили данные с cookie строкой."
        })

    token = cookies.get("__RequestVerificationToken", "")
    referer = parsed.get("referer", "")
    company_id = parsed.get("company_id")

    output = {
        "cookies": cookies,
        "token": token,
        "timestamp": time.time(),
        "datetime": time.strftime("%Y-%m-%d %H:%M:%S"),
        "referer": referer,
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 YaBrowser/26.6.0.0 Safari/537.36",
        "company_id": company_id
    }

    # Сохраняем файл
    script_dir = Path(__file__).parent.absolute()
    cookies_file = script_dir / "cookies_data.json"

    with open(cookies_file, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    return JSONResponse({
        "success": True,
        "cookie_count": len(cookies),
        "token": token,
        "company_id": company_id,
        "cookies": cookies,
        "output": output,
        "file_path": str(cookies_file)
    })


if __name__ == "__main__":
    import uvicorn
    print("=" * 60)
    print("🍪 Парсер cookies e-disclosure - FastAPI")
    print("=" * 60)
    print("\n🌐 Запуск сервера...")
    print("📋 Откройте в браузере: http://localhost:5000")
    print("\n📌 Поддерживаются два формата:")
    print("   1. Таблица cookies (копировать из Application → Cookies)")
    print("   2. Заголовки (Copy as cURL из Network)")
    print("\n⚠️  Для остановки нажмите Ctrl+C")
    print("=" * 60)

    uvicorn.run(app, host="127.0.0.1", port=5000)