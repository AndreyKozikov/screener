"""Репозиторий для работы с таблицей bond_float_params.

Содержит класс BondFloatParamsRepository для upsert и выборки параметров
плавающей ставки облигаций. Данные поступают из анализа эмиссионной
документации (GeminiBondAnalysisDTO). Одна запись на облигацию.
"""

import logging
from pathlib import Path
from typing import Optional

from sqlmodel import Session, create_engine, select

from app.models.entities.bond_float_params import BondFloatParams
from app.models.schemasDTO.gemini_dto import GeminiBondAnalysisDTO
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

    def upsert(self, bond_id: int, analysis: GeminiBondAnalysisDTO) -> None:
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

                    session.add(existing)
                    session.commit()
                    self.logger.info(
                        "Обновлены параметры флоатера для bond_id=%s", bond_id
                    )
                else:
                    record = BondFloatParams(
                        bond_id=bond_id,
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
