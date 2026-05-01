from pathlib import Path

# Корень проекта
PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent.parent

# Корень основного backend
BACKEND_DIR: Path = PROJECT_ROOT / "backend"

# Директория с JSON/CSV данными (columns.json, zerocupon.csv и т.д.)
DATA_DIR: Path = BACKEND_DIR / "app" / "data"

# JSON со всеми событиями эмитента с e-disclosure (по ИНН, без фильтрации по заголовку)
EMITENT_EVENTS_JSON_DIR: Path = DATA_DIR / "events"

# Файл базы данных SQLite (облигации, эмитенты, купоны и т.д.)
DB_PATH: Path = BACKEND_DIR / "db" / "bonds.db"

# Файл базы данных для истории торгов (отдельная БД)
HISTORY_DB_PATH: Path = BACKEND_DIR / "db" / "history_db.db"

# ——— API Мосбиржи ———
MOEX_BONDS_URL: str = "https://iss.moex.com/iss/engines/stock/markets/bonds/securities.json"
MOEX_BONDIZATION_BASE_URL: str = "https://iss.moex.com/iss/securities/{secid}/bondization.json"
MOEX_COUPONS_QUERY: str = "?iss.json=extended&iss.meta=off&iss.only=coupons&lang=ru&limit=unlimited"
MOEX_HISTORY_URL: str = "https://iss.moex.com/iss/history/engines/stock/markets/bonds/securities/{secid}.json"

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

FEEDBACK_FILE_PATH: Path = DATA_DIR / FEEDBACK_JSON
SENT_FEEDBACK_FILE_PATH: Path = DATA_DIR / SENT_FEEDBACK_JSON
ZEROCOUPON_CSV_PATH: Path = DATA_DIR / ZEROCOUPON_CSV
