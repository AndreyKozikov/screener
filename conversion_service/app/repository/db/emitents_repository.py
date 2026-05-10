import sqlite3
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from config.paths import DB_PATH

logger = logging.getLogger(__name__)

class EmitentsRepository:
    """Репозиторий для работы с эмитентами через Raw SQL."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or DB_PATH

    def get_emitent_id_by_inn(self, inn: str) -> Optional[int]:
        """Получает ID эмитента по ИНН."""
        query = "SELECT id FROM emitents WHERE inn = ?"
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(query, (inn,))
                row = cursor.fetchone()
                return row[0] if row else None
        except Exception as e:
            logger.error(f"Ошибка при получении emitent_id по ИНН {inn}: {e}")
            return None

    def get_emitents_with_inn(self) -> List[Dict[str, Any]]:
        """Возвращает список всех эмитентов, у которых заполнен ИНН."""
        query = "SELECT id, inn FROM emitents WHERE inn IS NOT NULL AND inn != ''"
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute(query)
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Ошибка при получении списка эмитентов с ИНН: {e}")
            return []
