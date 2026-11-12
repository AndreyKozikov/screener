from pathlib import Path

from conversion_service.config.config_loader import resolve_path
from conversion_service.config.settings import settings

# Корень проекта
PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent.parent

# Корень основного backend (используется только для общих файлов данных и логов)
BACKEND_DIR: Path = PROJECT_ROOT / "backend"

# Директория с JSON/CSV данными. Значение задаётся в config/config.toml.
DATA_DIR: Path = resolve_path(
    settings.DATA_DIR,
    PROJECT_ROOT / "backend" / "app" / "data",
)

# JSON со всеми событиями эмитента с e-disclosure (по ИНН, без фильтрации по заголовку)
EMITENT_EVENTS_JSON_DIR: Path = resolve_path(
    settings.EMITENT_EVENTS_JSON_DIR,
    DATA_DIR / "events",
)

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
