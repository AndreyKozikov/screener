import sqlite3
import logging
from pathlib import Path
from typing import Optional
from config.paths import DB_PATH

logger = logging.getLogger(__name__)

class EmitentEdisclosureRepository:
    """Репозиторий для маппинга ID e-disclosure через Raw SQL."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or DB_PATH

    def get_edisclosure_id_by_emitent_id(self, emitent_id: int) -> Optional[int]:
        """Получает edisclosure_id по внутреннему emitent_id."""
        query = "SELECT edisclosure_id FROM emitent_edisclosure WHERE emitent_id = ?"
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(query, (emitent_id,))
                row = cursor.fetchone()
                return row[0] if row else None
        except Exception as e:
            logger.error(f"Ошибка при получении edisclosure_id для emitent_id {emitent_id}: {e}")
            return None

    def upsert_mapping(self, emitent_id: int, edisclosure_id: int) -> None:
        """Обновляет или вставляет маппинг ID."""
        query = """
            INSERT INTO emitent_edisclosure (emitent_id, edisclosure_id)
            VALUES (?, ?)
            ON CONFLICT(emitent_id) DO UPDATE SET edisclosure_id = excluded.edisclosure_id
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(query, (emitent_id, edisclosure_id))
                conn.commit()
        except Exception as e:
            logger.error(f"Ошибка при сохранении маппинга emitent_id {emitent_id}: {e}")
            raise
