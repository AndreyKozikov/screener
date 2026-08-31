from pathlib import Path

# Корень backend (директория с main.py, app/, config/, db/)
BACKEND_DIR: Path = Path(__file__).resolve().parent.parent.parent / "backend"

# Директория с JSON/CSV данными (columns.json, zerocupon.csv и т.д.)
DATA_DIR: Path = BACKEND_DIR / "app" / "data"

# JSON со всеми событиями эмитента с e-disclosure (по ИНН, без фильтрации по заголовку)
EMITENT_EVENTS_JSON_DIR: Path = DATA_DIR / "events"

# Файл базы данных SQLite (облигации, эмитенты, купоны и т.д.)
print(BACKEND_DIR)
DB_PATH: Path = BACKEND_DIR / "db" / "bonds.db"

print(DB_PATH)