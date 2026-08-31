"""
Отдельный скрипт для получения cookies и токена из e-disclosure.ru.
Автоматический переход на страницу компании после поиска.
"""

import json
import time
import os
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


def get_cookies_and_token():
    """Запускает браузер, ищет компанию и переходит на её страницу."""

    print("=" * 70)
    print("🔵 ЗАПУСК БРАУЗЕРА ДЛЯ ПОЛУЧЕНИЯ COOKIES")
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
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

    try:
        # ШАГ 1: Открываем страницу поиска
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

        # ШАГ 2: Ищем поле ввода и вводим ИНН
        print("🔍 Ищу компанию по ИНН 0010000025...")

        # Поле ввода — ТОЧНО id="textfield"
        inn_input = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "textfield"))
        )
        inn_input.clear()
        inn_input.send_keys("0010000025")
        print("  ✅ Поле ввода найдено, ИНН введён")

        time.sleep(0.5)

        # ШАГ 3: Нажимаем кнопку "Искать" — ТОЧНО id="sendButton"
        try:
            search_btn = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.ID, "sendButton"))
            )
            search_btn.click()
            print("  ✅ Кнопка 'Искать' нажата")
        except Exception as e:
            print(f"  ⚠️ Не удалось нажать кнопку: {e}")
            print("  Пожалуйста, нажмите кнопку 'Искать' вручную")
            input("▶️  Нажмите ENTER после нажатия 'Искать' >>> ")

        time.sleep(3)

        # ШАГ 4: Ждём результаты и переходим на страницу компании
        try:
            print("🔗 Перехожу на страницу компании...")

            # Ищем ссылку на компанию
            company_link = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "a[href*='company.aspx?id=']"))
            )
            company_url = company_link.get_attribute("href")
            print(f"  ✅ Найдена ссылка: {company_url}")

            # Переходим по ссылке
            driver.get(company_url)
            time.sleep(2)
            print(f"  ✅ Переход выполнен на: {driver.current_url}")

        except Exception as e:
            print(f"  ⚠️ Не удалось автоматически найти ссылку: {e}")
            print("  Пожалуйста, перейдите на страницу компании вручную")
            input("▶️  Нажмите ENTER после перехода на страницу компании >>> ")

        # ШАГ 5: Собираем ВСЕ cookies
        print("\n🍪 Собираю все cookies...")
        all_cookies = driver.get_cookies()
        cookies_dict = {}
        for c in all_cookies:
            cookies_dict[c['name']] = c['value']
            print(f"  🍪 {c['name']} = {c['value'][:40]}...")

        print(f"\n✅ Итого cookies: {len(cookies_dict)} шт.")

        # ШАГ 6: Получаем токен
        print("🔑 Получаю токен...")
        token = driver.execute_script("""
            const input = document.querySelector('input[name="__RequestVerificationToken"]');
            return input ? input.value : '';
        """)

        if token:
            print(f"✅ Токен найден: {token[:40]}...")
        else:
            print("❌ Токен не найден!")

        # ШАГ 7: Сохраняем данные
        data = {
            "cookies": cookies_dict,
            "token": token,
            "timestamp": time.time(),
            "datetime": time.strftime("%Y-%m-%d %H:%M:%S"),
            "url": driver.current_url,
        }

        script_dir = Path(__file__).parent.absolute()
        cookies_file = script_dir / "cookies_data.json"

        with open(cookies_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        print(f"\n✅ Сохранено в: {cookies_file}")

        # Проверка
        critical = ['ASP.NET_SessionId', '.AspNetCore.Antiforgery', 'adtech_uid', 'top100_id']
        found = [c for c in critical if c in cookies_dict]
        missing = [c for c in critical if c not in cookies_dict]

        if found:
            print(f"\n✅ Найдены важные cookies: {found}")
        if missing:
            print(f"\n⚠️  Отсутствуют: {missing}")

        return data

    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
        return None
    finally:
        driver.quit()
        print("\n🔴 Браузер закрыт")


if __name__ == "__main__":
    get_cookies_and_token()