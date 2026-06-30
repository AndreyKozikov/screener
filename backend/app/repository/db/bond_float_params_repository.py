"""Репозиторий для работы с таблицей bond_float_params.

Содержит класс BondFloatParamsRepository для upsert и выборки параметров
плавающей ставки облигаций. Данные поступают из анализа эмиссионной
документации (GeminiBondAnalysisDTO). Одна запись на облигацию.
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from sqlmodel import Session, create_engine, select

from app.models.entities.bond_float_params import BondFloatParams
from app.models.schemasDTO.llm_floatbond_dto import LLMBondAnalysisDTO
from app.utils.logger import get_data_update_logger
from config.paths import DB_PATH


class BondFloatParamsRepository:
    """Репозиторий для CRUD-операций с параметрами флоатера (bond_float_params).

    Обеспечивает upsert результатов анализа эмиссионной документации
    и выборку по bond_id. Одна запись на облигацию (bond_id UNIQUE).
    """

    def __init__(self, db_path: Optional[Path] = None) -> None:
        """Инициализирует репозиторий.

        Args:
            db_path: Путь к файлу базы данных SQLite. Если не указан,
                используется backend/db/bonds.db.
        """
        if db_path is None:
            db_path = DB_PATH
        self.db_path = Path(db_path)
        self._engine = create_engine(
            f"sqlite:///{self.db_path.resolve()}",
            connect_args={"check_same_thread": False},
            echo=False,
        )
        self.logger = logging.getLogger(__name__)

    def upsert(self, bond_id: int, analysis: LLMBondAnalysisDTO) -> None:
        """Сохраняет или обновляет параметры флоатера для облигации.

        Если запись с данным bond_id уже существует — обновляет все поля.
        Если не существует — создаёт новую запись. Извлекает данные из
        float_params, calculation_engine и trading секций DTO.

        Args:
            bond_id: Идентификатор облигации (bonds.id).
            analysis: Результат анализа эмиссионной документации.
        """
        data_log = get_data_update_logger()
        fp = analysis.float_params
        ce = analysis.calculation_engine
        trading = analysis.trading

        try:
            with Session(self._engine) as session:
                stmt = select(BondFloatParams).where(
                    BondFloatParams.bond_id == bond_id
                )
                existing: Optional[BondFloatParams] = session.exec(stmt).first()

                if existing is not None:
                    existing.is_find = 1
                    existing.base_indicator_code = fp.base_indicator_code
                    existing.spread = fp.spread
                    existing.coupon_frequency_days = fp.coupon_frequency_days
                    existing.lookback_period = fp.lookback_period
                    existing.averaging_period = fp.averaging_period
                    existing.formula_raw = fp.formula_raw
                    existing.rate_determination_rule = fp.rate_determination_rule
                    existing.calculation_type = fp.calculation_type
                    existing.rounding_precision = fp.rounding_precision
                    existing.key_rate_method = fp.key_rate_method
                    existing.lookback_type = fp.lookback_type
                    existing.year_base = fp.year_base
                    existing.is_daily_accrual = fp.is_daily_accrual

                    existing.offset_days = ce.offset_days if ce else None
                    existing.offset_calendar = ce.offset_calendar if ce else None
                    existing.day_count = ce.day_count if ce else None
                    existing.fallback = ce.fallback if ce else None
                    existing.accrual_type = ce.accrual_type if ce else None
                    existing.interest_compounding = ce.interest_compounding if ce else False

                    existing.placement_date = trading.placement_date
                    existing.underwriter = trading.underwriter

                    existing.floor_rate = fp.floor_rate
                    existing.cap_rate = fp.cap_rate
                    existing.extra_indicators = fp.extra_indicators
                    existing.condition_logic = fp.condition_logic
                    existing.observation_type = fp.observation_type
                    existing.reference_period_desc = fp.reference_period_desc

                    session.add(existing)
                    session.commit()
                    self.logger.info(
                        "Обновлены параметры флоатера для bond_id=%s", bond_id
                    )
                else:
                    record = BondFloatParams(
                        bond_id=bond_id,
                        is_find=1,
                        base_indicator_code=fp.base_indicator_code,
                        spread=fp.spread,
                        coupon_frequency_days=fp.coupon_frequency_days,
                        lookback_period=fp.lookback_period,
                        averaging_period=fp.averaging_period,
                        formula_raw=fp.formula_raw,
                        rate_determination_rule=fp.rate_determination_rule,
                        calculation_type=fp.calculation_type,
                        rounding_precision=fp.rounding_precision,
                        key_rate_method=fp.key_rate_method,
                        lookback_type=fp.lookback_type,
                        year_base=fp.year_base,
                        is_daily_accrual=fp.is_daily_accrual,
                        offset_days=ce.offset_days if ce else None,
                        offset_calendar=ce.offset_calendar if ce else None,
                        day_count=ce.day_count if ce else None,
                        fallback=ce.fallback if ce else None,
                        accrual_type=ce.accrual_type if ce else None,
                        interest_compounding=ce.interest_compounding if ce else False,
                        placement_date=trading.placement_date,
                        underwriter=trading.underwriter,
                        floor_rate=fp.floor_rate,
                        cap_rate=fp.cap_rate,
                        extra_indicators=fp.extra_indicators,
                        condition_logic=fp.condition_logic,
                        observation_type=fp.observation_type,
                        reference_period_desc=fp.reference_period_desc,
                    )
                    session.add(record)
                    session.commit()
                    self.logger.info(
                        "Создана запись параметров флоатера для bond_id=%s", bond_id
                    )

            data_log.info(
                "[edisclosure] Параметры флоатера сохранены для bond_id=%s", bond_id
            )
        except Exception as e:
            data_log.error(
                "[edisclosure] Ошибка при сохранении параметров флоатера для bond_id=%s: %s",
                bond_id,
                e,
                exc_info=True,
            )
            self.logger.error(
                "Ошибка при upsert bond_float_params для bond_id=%s: %s",
                bond_id,
                e,
                exc_info=True,
            )

    def upsert_not_found(self, bond_id: int, data: Dict[str, Any]) -> None:
        """Сохраняет переданную запись «данные не найдены» для облигации.

        Структура данных (is_find=0, base_indicator_code="", остальное NULL)
        формируется в сервисе; репозиторий только применяет data к существующей
        или новой записи и сохраняет.

        Args:
            bond_id: Идентификатор облигации (bonds.id).
            data: Словарь полей bond_float_params (без id и bond_id).
        """
        try:
            with Session(self._engine) as session:
                stmt = select(BondFloatParams).where(
                    BondFloatParams.bond_id == bond_id
                )
                existing: Optional[BondFloatParams] = session.exec(stmt).first()

                if existing is not None:
                    for key, value in data.items():
                        if hasattr(existing, key):
                            setattr(existing, key, value)
                    session.add(existing)
                else:
                    record = BondFloatParams(bond_id=bond_id, **data)
                    session.add(record)
                session.commit()
                self.logger.info(
                    "Сохранена запись is_find=0 (данные не найдены) для bond_id=%s",
                    bond_id,
                )
        except Exception as e:
            self.logger.error(
                "Ошибка при upsert_not_found для bond_id=%s: %s",
                bond_id,
                e,
                exc_info=True,
            )

    def get_existing_bond_ids(self) -> Set[int]:
        """Возвращает множество bond_id всех записей в bond_float_params.

        Returns:
            Множество идентификаторов облигаций, для которых уже есть запись.
            Пустое множество при ошибке.
        """
        try:
            with Session(self._engine) as session:
                stmt = select(BondFloatParams.bond_id)
                rows = session.exec(stmt).all()
                return {int(r) for r in rows}
        except Exception as e:
            self.logger.error(
                "Ошибка при получении существующих bond_id: %s", e, exc_info=True
            )
            return set()

    def get_bond_ids_with_find(self) -> List[int]:
        """Возвращает список bond_id записей с is_find != 0.

        Returns:
            Список идентификаторов облигаций, для которых найдены параметры
            флоатера. Пустой список при ошибке.
        """
        try:
            with Session(self._engine) as session:
                stmt = select(BondFloatParams.bond_id).where(
                    BondFloatParams.is_find != 0
                )
                rows = session.exec(stmt).all()
                return [int(r) for r in rows]
        except Exception as e:
            self.logger.error(
                "Ошибка при получении bond_ids с is_find != 0: %s", e, exc_info=True
            )
            return []

    def get_by_bond_id(self, bond_id: int) -> Optional[BondFloatParams]:
        """Возвращает параметры флоатера по bond_id.

        Args:
            bond_id: Идентификатор облигации (bonds.id).

        Returns:
            Объект BondFloatParams или None, если запись не найдена.
        """
        try:
            with Session(self._engine) as session:
                stmt = select(BondFloatParams).where(
                    BondFloatParams.bond_id == bond_id
                )
                return session.exec(stmt).first()
        except Exception as e:
            self.logger.error(
                "Ошибка при получении bond_float_params для bond_id=%s: %s",
                bond_id,
                e,
                exc_info=True,
            )
            return None
