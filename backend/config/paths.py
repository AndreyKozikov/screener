"""Пути к файлам данных, БД и адреса API Мосбиржи.

Все пути и URL вынесены сюда; скрипты и модули импортируют их из этого модуля.
Корень backend — директория, в которой лежат main.py и папка config.
"""

from pathlib import Path


# Корень backend (директория с main.py, app/, config/, db/)
BACKEND_DIR: Path = Path(__file__).resolve().parent.parent

# Директория с JSON/CSV данными (columns.json, zerocupon.csv и т.д.)
DATA_DIR: Path = BACKEND_DIR / "app" / "data"

# JSON со всеми событиями эмитента с e-disclosure (по ИНН, без фильтрации по заголовку)
EMITENT_EVENTS_JSON_DIR: Path = DATA_DIR / "events"

# Файл базы данных SQLite (облигации, эмитенты, купоны и т.д.)
DB_PATH: Path = BACKEND_DIR / "db" / "bonds.db"

# Файл базы данных SQLite для блога.
BLOG_DB_PATH: Path = BACKEND_DIR / "db" / "blog.db"

# Файл базы данных для истории торгов (отдельная БД)
HISTORY_DB_PATH: Path = BACKEND_DIR / "db" / "history_db.db"

# Файл .env (переменные окружения)
ENV_FILE: Path = BACKEND_DIR / ".env"

# ——— API Мосбиржи ———
MOEX_BONDS_URL: str = (
    "https://iss.moex.com/iss/engines/stock/markets/bonds/securities.json"
)
"""URL для загрузки списка облигаций (securities)."""

MOEX_BONDIZATION_BASE_URL: str = (
    "https://iss.moex.com/iss/securities/{secid}/bondization.json"
)
"""Базовый URL API для данных по облигации (купоны, амортизация, оферты)."""

MOEX_COUPONS_QUERY: str = (
    "?iss.json=extended&iss.meta=off&iss.only=coupons&lang=ru&limit=unlimited"
)
"""Суффикс запроса для получения купонов в bondization API."""

MOEX_HISTORY_URL: str = (
    "https://iss.moex.com/iss/history/engines/stock/markets/bonds"
    "/securities/{secid}.json"
)
"""Базовый URL API для истории торгов по облигации."""

# ——— Имена файлов данных (в DATA_DIR) ———
BONDS_JSON: str = "bonds.json"
BONDS_RATING_JSON: str = "bonds_rating.json"
BONDS_TYPE_MAPPING_JSON: str = "bonds_type_mapping.json"
BONDS_TYPE43_MAPPING_JSON: str = "bonds_type43_mapping.json"
COLUMNS_JSON: str = "columns.json"
ZEROCOUPON_CSV: str = "zerocupon.csv"
HISTORY_JSON: str = "bonds_trading_history.json"
FEEDBACK_JSON: str = "feedback.json"
SENT_FEEDBACK_JSON: str = "sent_feedback.json"

# Полные пути к часто используемым файлам
FEEDBACK_FILE_PATH: Path = DATA_DIR / FEEDBACK_JSON
SENT_FEEDBACK_FILE_PATH: Path = DATA_DIR / SENT_FEEDBACK_JSON
ZEROCOUPON_CSV_PATH: Path = DATA_DIR / ZEROCOUPON_CSV
BLOG_UPLOADS_DIR: Path = DATA_DIR / "blog" / "uploads"
