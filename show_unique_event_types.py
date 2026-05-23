import sqlite3
import sys

# Настройка вывода для корректного отображения кириллицы в консоли
sys.stdout.reconfigure(encoding='utf-8')

def show_classes():
    try:
        conn = sqlite3.connect('classification/bonds.db')
        c = conn.cursor()
        
        # Получаем все уникальные значения из event_type
        c.execute("SELECT DISTINCT event_type FROM events_details WHERE event_type IS NOT NULL AND TRIM(event_type) != ''")
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
