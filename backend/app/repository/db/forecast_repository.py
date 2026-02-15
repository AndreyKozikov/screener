"""Репозиторий для таблиц среднесрочного прогноза Банка России.

Только вставка/замена данных: по дате прогноза удаляются старые записи (forecast,
forecast_main_indicators, forecast_balance), затем вставляются новые.
forecast_indicator_name — общий справочник, merge по (section, key).
"""

from datetime import date
from pathlib import Path
from typing import List, Optional, Tuple

from sqlmodel import Session, create_engine, select

from app.models.entities.forecast import (
    Forecast,
    ForecastBalance,
    ForecastIndicatorName,
    ForecastMainIndicators,
)
from app.utils.logger import get_data_update_logger
from config.paths import DB_PATH


class ForecastRepository:
    """Репозиторий для вставки данных прогноза в таблицы forecast, forecast_indicator_name, forecast_main_indicators, forecast_balance."""

    def __init__(self, db_path: Optional[Path] = None) -> None:
        if db_path is None:
            db_path = DB_PATH
        self.db_path = Path(db_path)
        self._engine = create_engine(
            f"sqlite:///{self.db_path.resolve()}",
            connect_args={"check_same_thread": False},
            echo=False,
        )
        self._log = get_data_update_logger()

    def get_all_dates(self) -> List[date]:
        """Возвращает все даты прогнозов из таблицы forecast (сырые данные для сервиса).

        Сортировка: от новых к старым. Пустой список, если таблица пуста или недоступна.
        """
        try:
            with Session(self._engine) as session:
                stmt = select(Forecast.date).order_by(Forecast.date.desc())
                rows = session.exec(stmt).all()
                # Одна колонка: строка может быть Row (row[0]) или скаляр (row)
                out = []
                for row in rows:
                    if hasattr(row, "__getitem__") and len(row) == 1:
                        out.append(row[0])
                    else:
                        out.append(row)
                return out
        except Exception as e:
            self._log.debug("[FORECAST] get_all_dates: %s", e)
            return []

    def get_forecast_by_date(
        self, forecast_date: date
    ) -> Optional[
        Tuple[
            Forecast,
            List[ForecastIndicatorName],
            List[ForecastMainIndicators],
            List[ForecastBalance],
        ]
    ]:
        """Возвращает данные прогноза по дате: meta, список названий показателей, основные показатели, платёжный баланс. None, если даты нет."""
        try:
            with Session(self._engine) as session:
                meta = session.get(Forecast, forecast_date)
                if meta is None:
                    return None
                names_stmt = select(ForecastIndicatorName)
                names_rows = list(session.exec(names_stmt).all())
                names_list: List[ForecastIndicatorName] = []
                for row in names_rows:
                    if hasattr(row, "__getitem__") and len(row) == 1:
                        names_list.append(row[0])
                    else:
                        names_list.append(row)
                main_stmt = (
                    select(ForecastMainIndicators)
                    .where(ForecastMainIndicators.forecast_date == forecast_date)
                    .order_by(ForecastMainIndicators.year)
                )
                main_rows = list(session.exec(main_stmt).all())
                main_list: List[ForecastMainIndicators] = []
                for row in main_rows:
                    if hasattr(row, "__getitem__") and len(row) == 1:
                        main_list.append(row[0])
                    else:
                        main_list.append(row)
                balance_stmt = (
                    select(ForecastBalance)
                    .where(ForecastBalance.forecast_date == forecast_date)
                    .order_by(ForecastBalance.year)
                )
                balance_rows = list(session.exec(balance_stmt).all())
                balance_list: List[ForecastBalance] = []
                for row in balance_rows:
                    if hasattr(row, "__getitem__") and len(row) == 1:
                        balance_list.append(row[0])
                    else:
                        balance_list.append(row)
                return (meta, names_list, main_list, balance_list)
        except Exception as e:
            self._log.debug("[FORECAST] get_forecast_by_date: %s", e)
            return None

    def save_forecast(
        self,
        meta: Forecast,
        indicator_names: List[ForecastIndicatorName],
        main_indicators: List[ForecastMainIndicators],
        balance_rows: List[ForecastBalance],
    ) -> bool:
        """Заменяет данные по дате прогноза и вставляет переданные записи.

        При повторной загрузке отчёта с той же датой (meta.date) существующие данные
        перезаписываются: для этой даты удаляются строки в forecast_balance,
        forecast_main_indicators и forecast, затем вставляются новые meta, indicator_names
        (merge по (section, key)), main_indicators, balance_rows.
        """
        forecast_date = meta.date
        try:
            with Session(self._engine) as session:
                # Удаление по дате (сначала дочерние таблицы, затем forecast)
                for row in list(session.exec(select(ForecastBalance).where(ForecastBalance.forecast_date == forecast_date))):
                    session.delete(row)
                for row in list(session.exec(select(ForecastMainIndicators).where(ForecastMainIndicators.forecast_date == forecast_date))):
                    session.delete(row)
                existing = session.get(Forecast, forecast_date)
                if existing:
                    session.delete(existing)
                session.commit()
            with Session(self._engine) as session:
                session.add(meta)
                for name_row in indicator_names:
                    session.merge(name_row)
                for main_row in main_indicators:
                    session.add(main_row)
                for balance_row in balance_rows:
                    session.add(balance_row)
                session.commit()
            self._log.info(
                "[FORECAST] Сохранён прогноз за %s: main=%s, balance=%s (база: %s)",
                forecast_date.isoformat(),
                len(main_indicators),
                len(balance_rows),
                self.db_path,
            )
            return True
        except Exception as e:
            self._log.error("[FORECAST] Ошибка записи прогноза: %s", e, exc_info=True)
            return False