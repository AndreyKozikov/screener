from pathlib import Path

# Данные и базы данных остаются в backend, но обслуживаются только этим сервисом.
BACKEND_DIR: Path = Path(__file__).resolve().parent.parent.parent / "backend"

# Директория с JSON/CSV данными (columns.json, zerocupon.csv и т.д.)
DATA_DIR: Path = BACKEND_DIR / "app" / "data"

# JSON со всеми событиями эмитента с e-disclosure (по ИНН, без фильтрации по заголовку)
EMITENT_EVENTS_JSON_DIR: Path = DATA_DIR / "events"

# Файл базы данных SQLite (облигации, эмитенты, купоны и т.д.)
DB_PATH: Path = BACKEND_DIR / "db" / "bonds.db"
BLOG_DB_PATH: Path = BACKEND_DIR / "db" / "blog.db"
HISTORY_DB_PATH: Path = BACKEND_DIR / "db" / "history_db.db"
