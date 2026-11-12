"""Пути к локальным файлам приложения.

Корень backend — директория, в которой лежат main_db.py и папка config.
"""

from pathlib import Path

from config.config_loader import load_config, resolve_path


# Корень backend (директория с main.py, app/, config/, db/)
BACKEND_DIR: Path = Path(__file__).resolve().parent.parent

# Директория с JSON/CSV данными (columns.json, zerocupon.csv и т.д.).
# Значение можно переопределить в backend/config/config.toml: [paths] data_dir.
_config = load_config()
_configured_data_dir = _config.get("paths", {}).get("data_dir")
DATA_DIR: Path = resolve_path(
    _configured_data_dir,
    BACKEND_DIR / "app" / "data",
)

# JSON со всеми событиями эмитента с e-disclosure (по ИНН, без фильтрации по заголовку)
EMITENT_EVENTS_JSON_DIR: Path = DATA_DIR / "events"

# Файл .env (переменные окружения)
ENV_FILE: Path = BACKEND_DIR / ".env"

# ——— Имена файлов данных (в DATA_DIR) ———
BONDS_TYPE_MAPPING_JSON: str = "bonds_type_mapping.json"
BONDS_TYPE43_MAPPING_JSON: str = "bonds_type43_mapping.json"
COLUMNS_JSON: str = "columns.json"
FEEDBACK_JSON: str = "feedback.json"
SENT_FEEDBACK_JSON: str = "sent_feedback.json"

# Полные пути к часто используемым файлам
FEEDBACK_FILE_PATH: Path = DATA_DIR / FEEDBACK_JSON
SENT_FEEDBACK_FILE_PATH: Path = DATA_DIR / SENT_FEEDBACK_JSON
BLOG_UPLOADS_DIR: Path = DATA_DIR / "blog" / "uploads"
