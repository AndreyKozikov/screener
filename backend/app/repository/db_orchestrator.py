import logging
from pathlib import Path
from typing import Any, Dict, Optional

from sqlmodel import Session, create_engine

from app.core.bond_transformer import BondTransformer
from config.paths import DATA_DIR as DEFAULT_DATA_DIR, DB_PATH as DEFAULT_DB_PATH
from app.repository.db.bonds_repository import BondsRepository
from app.repository.db.db_coupon import DBCoupon
from app.repository.db.db_kbd import KbdRepository
from app.repository.files.file_storage import FileStorage
from app.services import bonds_service
from app.services.emitent_service import get_emitent_service
from app.utils.logger import get_data_update_logger


class DBOrchestrator:
    """Главный скрипт для управления миграцией данных в базу данных"""
    
    def __init__(self, db_path: Optional[Path] = None, data_dir: Optional[Path] = None):
        """
        Инициализация оркестратора
        
        Args:
            db_path: Путь к файлу базы данных. Если не указан, используется backend/db/bonds.db
            data_dir: Путь к директории с JSON-файлами. Если не указан, используется backend/app/data
        """
        self.db_path = db_path if db_path is not None else DEFAULT_DB_PATH
        self.data_dir = data_dir if data_dir is not None else DEFAULT_DATA_DIR
        self.logger = logging.getLogger(__name__)
    
    def _migrate_coupons(self) -> bool:
        """Создаёт таблицу coupons при отсутствии. Данные купонов — только из API MOEX.

        Вызов refresh создаёт таблицу; заполнение выполняется через
        save_coupons_bulk после загрузки с MOEX (endpoint /bonds/refresh-coupons).

        Returns:
            True если таблица создана/проверена успешно, False в случае ошибки.
        """
        try:
            db_coupon = DBCoupon(db_path=str(self.db_path))
            db_coupon.refresh("coupons", secid_to_id=None)
            self.logger.info("Таблица coupons проверена/создана")
            return True
        except Exception as e:
            self.logger.error("Ошибка при миграции таблицы coupons: %s", e, exc_info=True)
            return False
    
    def update_coupons(
        self,
        update_coupons: bool,
        data_downloaded_from_server: bool = True,
        data_saved_to_file: bool = True,
        table_name: str = "coupons"
    ) -> bool:
        """
        Обновляет данные купонов в базе данных при выполнении условий.
        
        Выполняется только если:
        - update_coupons == True (флаг обновления данных по купонам из чекбокса фронтенда)
        - data_downloaded_from_server == True (данные успешно загружены с сервера)
        - data_saved_to_file == True (данные успешно сохранены в файл)
        
        Args:
            update_coupons: Флаг обновления данных по купонам из чекбокса фронтенда
            data_downloaded_from_server: Флаг успешной загрузки данных с сервера
            data_saved_to_file: Флаг успешного сохранения данных в файл
            table_name: Имя таблицы для работы в БД (по умолчанию "coupons")
        
        Returns:
            True если обновление выполнено успешно, False в противном случае
        """
        if not (update_coupons and data_downloaded_from_server and data_saved_to_file):
            self.logger.debug(
                f"Обновление купонов пропущено: "
                f"update_coupons={update_coupons}, "
                f"data_downloaded_from_server={data_downloaded_from_server}, "
                f"data_saved_to_file={data_saved_to_file}"
            )
            return False
        
        self.logger.info("Запуск обновления данных купонов")
        return self._migrate_coupons()
    
    def _migrate_kbd(self) -> bool:
        """
        Резерв для типа миграции "kbd". Таблица kbd создаётся Alembic;
        данные загружаются через API в эндпоинте /api/zerocupon/refresh.
        """
        self.logger.info("Миграция kbd: таблица управляется Alembic, данные — через API")
        return True
    
    def update_kbd(
        self,
        update_zero_coupon_curve: bool,
        data_downloaded_from_server: bool = True,
        data_saved_to_file: bool = True,
        table_name: str = "kbd"
    ) -> bool:
        """
        Обновляет данные кривой бескупонной доходности в базе данных при выполнении условий.
        
        Выполняется только если:
        - update_zero_coupon_curve == True (флаг обновления данных кривой бескупонной доходности из чекбокса фронтенда)
        - data_downloaded_from_server == True (данные успешно загружены с сервера)
        - data_saved_to_file == True (данные успешно сохранены в файл)
        
        Args:
            update_zero_coupon_curve: Флаг обновления данных кривой бескупонной доходности из чекбокса фронтенда
            data_downloaded_from_server: Флаг успешной загрузки данных с сервера
            data_saved_to_file: Флаг успешного сохранения данных в файл
            table_name: Имя таблицы для работы в БД (по умолчанию "kbd")
        
        Returns:
            True если обновление выполнено успешно, False в противном случае
        """
        if not (update_zero_coupon_curve and data_downloaded_from_server and data_saved_to_file):
            self.logger.debug(
                f"Обновление KBD пропущено: "
                f"update_zero_coupon_curve={update_zero_coupon_curve}, "
                f"data_downloaded_from_server={data_downloaded_from_server}, "
                f"data_saved_to_file={data_saved_to_file}"
            )
            return False
        
        self.logger.info("Запуск обновления данных кривой бескупонной доходности")
        return self._migrate_kbd()
