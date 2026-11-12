import sqlite3
import sys
from pathlib import Path

# Настройка вывода для корректного отображения кириллицы в консоли
sys.stdout.reconfigure(encoding="utf-8")

# Разрешить запуск как из корня репозитория, так и из db_repository/tools.
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from db_repository.config.paths import DB_PATH


def show_classes():
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()

        # Получаем все уникальные значения из event_type
        c.execute(
            "SELECT DISTINCT event_type FROM events_details "
            "WHERE event_type IS NOT NULL AND TRIM(event_type) != ''"
        )
        rows = c.fetchall()

        # Сортируем для удобства чтения
        unique_types = sorted([row[0] for row in rows])

        print(f"=== УНИКАЛЬНЫЕ КЛАССЫ ИЗ СТОЛБЦА EVENT_TYPE (Всего: {len(unique_types)}) ===")
        print("-" * 50)
        for i, etype in enumerate(unique_types, 1):
            print(f"{i:3}. {etype}")

        conn.close()
    except Exception as e:
        print(f"Ошибка при работе с базой: {e}")


if __name__ == "__main__":
    show_classes()
