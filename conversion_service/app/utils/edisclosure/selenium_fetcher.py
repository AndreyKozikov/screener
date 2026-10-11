"""Legacy Selenium-based cookie fetcher for e-disclosure.ru.

Opens a Chrome browser using Selenium WebDriver, navigates to the
e-disclosure.ru search page, and waits for the user to manually pass
the Cloudflare/captcha challenge. After the user confirms, it
extracts cookies and the CSRF token.

This module is a **fallback** — prefer ``cloudflare_bypass.py``
(DrissionPage) for automated bypass. Use this only when DrissionPage
is unavailable or when explicit Selenium-based control is needed.
"""

import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


def get_cookies_via_selenium() -> Optional[Dict[str, Any]]:
    """Launch Chrome via Selenium and collect cookies after manual captcha.

    The user must pass the Cloudflare challenge manually in the opened
    browser window, then press Enter in the console.

    Returns:
        Dictionary with ``cookies``, ``token``, ``timestamp``, ``datetime``,
        and ``url``. Returns ``None`` on failure.
    """
    try:
        from selenium import webdriver
        from selenium.webdriver.common.by import By
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
    except ImportError:
        logger.error(
            "Selenium is not installed. Install with: pip install selenium"
        )
        return None

    print("=" * 70)
    print("🔵 ЗАПУСК БРАУЗЕРА ДЛЯ ПОЛУЧЕНИЯ COOKIES (Selenium)")
    print("=" * 70)

    options = Options()
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")

    driver = webdriver.Chrome(options=options)
    driver.execute_script(
        "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
    )

    try:
        # Step 1: Open search page
        print("🌐 Открываю страницу поиска...")
        driver.get("https://www.e-disclosure.ru/poisk-po-kompaniyam")

        print("\n" + "=" * 70)
        print("⚠️  ПРОЙДИТЕ КАПЧУ ВРУЧНУЮ")
        print("=" * 70)
        print("1️⃣ Если появилась капча с ползунком — подвиньте её")
        print("2️⃣ Дождитесь загрузки страницы поиска")
        print("3️⃣ Нажмите ENTER в консоли")
        print("=" * 70)

        input("▶️  Нажмите ENTER после прохождения капчи >>> ")
        time.sleep(2)

        # Step 2: Search for a company by INN
        print("🔍 Ищу компанию по ИНН 0010000025...")
        inn_input = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "textfield"))
        )
        inn_input.clear()
        inn_input.send_keys("0010000025")
        print("  ✅ Поле ввода найдено, ИНН введён")

        time.sleep(0.5)

        # Step 3: Click "Search" button
        try:
            search_btn = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.ID, "sendButton"))
            )
            search_btn.click()
            print("  ✅ Кнопка 'Искать' нажата")
        except Exception as exc:
            print(f"  ⚠️ Не удалось нажать кнопку: {exc}")
            print("  Пожалуйста, нажмите кнопку 'Искать' вручную")
            input("▶️  Нажмите ENTER после нажатия 'Искать' >>> ")

        time.sleep(3)

        # Step 4: Navigate to company page
        try:
            print("🔗 Перехожу на страницу компании...")
            company_link = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable(
                    (By.CSS_SELECTOR, "a[href*='company.aspx?id=']")
                )
            )
            company_url = company_link.get_attribute("href")
            print(f"  ✅ Найдена ссылка: {company_url}")
            driver.get(company_url)
            time.sleep(2)
            print(f"  ✅ Переход выполнен на: {driver.current_url}")
        except Exception as exc:
            print(f"  ⚠️ Не удалось автоматически найти ссылку: {exc}")
            print("  Пожалуйста, перейдите на страницу компании вручную")
            input("▶️  Нажмите ENTER после перехода на страницу компании >>> ")

        # Step 5: Collect cookies
        print("\n🍪 Собираю все cookies...")
        all_cookies = driver.get_cookies()
        cookies_dict: Dict[str, str] = {}
        for c in all_cookies:
            cookies_dict[c["name"]] = c["value"]
            display_val = c["value"][:40] + "..." if len(c["value"]) > 40 else c["value"]
            print(f"  🍪 {c['name']} = {display_val}")

        print(f"\n✅ Итого cookies: {len(cookies_dict)} шт.")

        # Step 6: Extract token
        print("🔑 Получаю токен...")
        token = driver.execute_script(
            "const input = document.querySelector("
            "'input[name=\"__RequestVerificationToken\"]');"
            "return input ? input.value : '';"
        )

        if token:
            print(f"✅ Токен найден: {token[:40]}...")
        else:
            print("❌ Токен не найден!")

        # Step 7: Save via CookieManager
        from app.utils.edisclosure.cookie_manager import get_cookie_manager

        manager = get_cookie_manager()
        saved_path = manager.save_cookies(
            cookies_dict,
            token,
            extra={"url": driver.current_url},
        )
        manager.invalidate()  # Force re-read on next use
        print(f"\n✅ Сохранено через CookieManager: {saved_path}")

        # Validate critical cookies
        critical = [
            "ASP.NET_SessionId",
            ".AspNetCore.Antiforgery",
            "adtech_uid",
            "top100_id",
        ]
        found = [c for c in critical if c in cookies_dict]
        missing = [c for c in critical if c not in cookies_dict]

        if found:
            print(f"\n✅ Найдены важные cookies: {found}")
        if missing:
            print(f"\n⚠️  Отсутствуют: {missing}")

        return {
            "cookies": cookies_dict,
            "token": token,
            "timestamp": time.time(),
            "datetime": time.strftime("%Y-%m-%d %H:%M:%S"),
            "url": driver.current_url,
        }

    except Exception as exc:
        logger.error("Selenium cookie fetch error: %s", exc, exc_info=True)
        print(f"❌ Ошибка: {exc}")
        return None
    finally:
        driver.quit()
        print("\n🔴 Браузер закрыт")


if __name__ == "__main__":
    get_cookies_via_selenium()
