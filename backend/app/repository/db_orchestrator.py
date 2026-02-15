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
    
    def migrate(self, migration_type: str, payload: Optional[Dict[str, Any]] = None) -> bool:
        """
        Главный метод для запуска миграции данных.

        Args:
            migration_type: Тип миграции (например, 'bonds' для облигаций).
            payload: Для migration_type == "bonds" — обязательный JSON-ответ MOEX.
                Чтение из файла не выполняется.

        Returns:
            True если миграция выполнена успешно, False в случае ошибки.
        """
        self.logger.info("Запуск миграции данных: %s", migration_type)

        try:
            if migration_type == "bonds":
                return self._migrate_bonds(payload=payload)
            elif migration_type == "coupons":
                return self._migrate_coupons()
            elif migration_type == "kbd":
                return self._migrate_kbd()
            else:
                self.logger.warning(f"Неизвестный тип миграции: {migration_type}")
                return False
        except Exception as e:
            self.logger.error(f"Ошибка при выполнении миграции {migration_type}: {str(e)}", exc_info=True)
            return False
    
    def _migrate_bonds(self, payload: Optional[Dict[str, Any]] = None) -> bool:
        """Выполняет миграцию данных облигаций в базу данных.

        Использует только переданный payload (ответ MOEX). Чтение из файла запрещено.

        Пайплайн: transform_raw_payload(payload) -> prepare_bonds_for_db -> transform_batch
        -> сохранение в таблицы bonds, bondsecurity, bondmarketdata, bondmarketdatayield.

        Args:
            payload: JSON-ответ MOEX (securities, marketdata, marketdata_yields).
                Обязателен; при отсутствии возбуждается ValueError.

        Returns:
            True если миграция выполнена успешно, False в случае ошибки.

        Raises:
            ValueError: Если payload не передан (чтение из файла не поддерживается).
        """
        if payload is None:
            raise ValueError(
                "Миграция облигаций требует payload (ответ MOEX). "
                "Чтение из файла отключено. Передайте payload в migrate('bonds', payload=...)."
            )
        data_log = get_data_update_logger()
        try:
            data_log.info(
                "[API /bonds/refresh] Начало сохранения данных облигаций в БД "
                "(таблицы bonds, bondsecurity, bondmarketdata, bondmarketdatayield)"
            )
            data_dir = self.data_dir
            storage = FileStorage()
            engine = create_engine(
                f"sqlite:///{self.db_path.resolve()}",
                connect_args={"check_same_thread": False},
                echo=False,
            )
            with Session(engine) as session:
                transformer = BondTransformer(data_dir, storage, session)
                raw_bonds = transformer.transform_raw_payload(payload)
                raw_bonds = transformer.prepare_bonds_for_db(raw_bonds)
            data_log.info(
                "[API /bonds/refresh] Загружено из JSON (MOEX): %s облигаций",
                len(raw_bonds),
            )
            self.logger.info("Загружено %s облигаций из JSON-файлов", len(raw_bonds))

            ready_bonds = transformer.transform_batch(raw_bonds)

            data_log.info(
                "[API /bonds/refresh] Преобразовано для таблицы bonds: %s записей",
                len(ready_bonds),
            )
            self.logger.info("Преобразовано %s облигаций для вставки в БД", len(ready_bonds))
            repo = BondsRepository(db_path=self.db_path)

            # 2. Сохраняем bonds (INSERT ON CONFLICT, без DELETE)
            bonds_ok = repo.refresh(ready_bonds)
            if not bonds_ok:
                data_log.warning(
                    "[API /bonds/refresh] Сохранение в таблицу bonds завершилось с ошибкой"
                )
                self.logger.warning("Миграция данных облигаций завершилась с ошибкой")
                return False

            # Преобразуем связанные таблицы (secid, boardid в каждой записи, bond_id через подзапрос)
            bond_securities = transformer.transform_to_bond_securities_batch(raw_bonds)
            bond_market_data = transformer.transform_to_bond_market_data_batch(raw_bonds)
            bond_market_data_yields = transformer.transform_to_bond_market_data_yields_batch(
                raw_bonds
            )
            data_log.info(
                "[API /bonds/refresh] Преобразовано BondSecurity: %s, BondMarketData: %s, "
                "BondMarketDataYield: %s",
                len(bond_securities),
                len(bond_market_data),
                len(bond_market_data_yields),
            )
            sec_ok = repo.save_bond_securities(bond_securities)
            md_ok = repo.save_bond_market_data(bond_market_data)
            yields_ok = repo.save_bond_market_data_yields(bond_market_data_yields)
            if not sec_ok:
                data_log.warning(
                    "[API /bonds/refresh] Сохранение в bondsecurity завершилось с ошибкой"
                )
            if not md_ok:
                data_log.warning(
                    "[API /bonds/refresh] Сохранение в bondmarketdata завершилось с ошибкой"
                )
            if not yields_ok:
                data_log.warning(
                    "[API /bonds/refresh] Сохранение в bondmarketdatayield завершилось с ошибкой"
                )

            # Дозаполнение эмитентов для облигаций без emitent_id
            try:
                data_log.info(
                    "[API /bonds/refresh] Шаг: отбор облигаций без проставленного эмитента"
                )
                secids_without_emitent = bonds_service.get_secids_without_emitent(
                    self.db_path
                )
                data_log.info(
                    "[API /bonds/refresh] Найдено облигаций без эмитента: %s",
                    len(secids_without_emitent),
                )
                if secids_without_emitent:
                    emitent_svc = get_emitent_service()
                    emitent_result = emitent_svc.refresh_emitents_for_secids(
                        secids_without_emitent, self.db_path
                    )
                    data_log.info(
                        "[API /bonds/refresh] Дозаполнение эмитентов: загружено=%s, "
                        "связано с bonds=%s, ошибок=%s",
                        emitent_result.get("updated", 0),
                        emitent_result.get("bonds_linked", 0),
                        emitent_result.get("errors", 0),
                    )
                else:
                    data_log.info(
                        "[API /bonds/refresh] Дозаполнение эмитентов пропущено (нет записей без эмитента)"
                    )
            except Exception as e:
                data_log.warning(
                    "[API /bonds/refresh] Ошибка при дозаполнении эмитентов: %s",
                    e,
                    exc_info=True,
                )
                self.logger.warning(
                    "Ошибка при дозаполнении эмитентов после миграции облигаций: %s",
                    e,
                )

            # Дозаполнение рейтингов для облигаций без rating (из bond_ratings и emitent_ratings)
            try:
                data_log.info(
                    "[API /bonds/refresh] Шаг: отбор облигаций без рейтинга"
                )
                secids_without_rating = bonds_service.get_secids_without_rating(
                    self.db_path
                )
                count_without_rating = len(secids_without_rating)
                data_log.info(
                    "[API /bonds/refresh] Из таблицы bonds отобрано облигаций с отсутствующим рейтингом: %s",
                    count_without_rating,
                )
                if secids_without_rating:
                    updated_ratings = bonds_service.fill_ratings_for_bonds_without_rating(
                        self.db_path
                    )
                    data_log.info(
                        "[API /bonds/refresh] Дозаполнение рейтингов: облигаций с отсутствующим рейтингом отобрано %s, записей обновлено (рейтинг проставлен): %s",
                        count_without_rating,
                        updated_ratings,
                    )
                else:
                    data_log.info(
                        "[API /bonds/refresh] Дозаполнение рейтингов пропущено (нет записей без рейтинга)"
                    )
            except Exception as e:
                data_log.warning(
                    "[API /bonds/refresh] Ошибка при дозаполнении рейтингов: %s",
                    e,
                    exc_info=True,
                )
                self.logger.warning(
                    "Ошибка при дозаполнении рейтингов после миграции облигаций: %s",
                    e,
                )

            overall = bonds_ok and sec_ok and md_ok and yields_ok
            if overall:
                self.logger.info("Миграция данных облигаций выполнена успешно")
            return overall
        except Exception as e:
            data_log.exception(
                "[API /bonds/refresh] Ошибка при сохранении в таблицу bonds: %s",
                e,
            )
            self.logger.exception("Ошибка при миграции данных облигаций: %s", e)
            raise
    
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
