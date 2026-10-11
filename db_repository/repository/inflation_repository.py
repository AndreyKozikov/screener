from typing import Optional, Any
from db_repository.models.inflations import InflationExpectations, InflationData
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy import select
from db_repository.core.database_init import get_session
from datetime import date


class InflationRepository:

    def __init__(self):
        pass

    def inflation_expectations_update(self, data: list[dict[str, Any]]):
        stmt = insert(InflationExpectations).values(data)

        stmt = stmt.on_conflict_do_update(
            index_elements=[InflationExpectations.recorddata],
            set_={
                "observed_annual_inflation": stmt.excluded.observed_annual_inflation,
                "expected_annual_inflation": stmt.excluded.expected_annual_inflation,
                "expected_five_year_inflation": stmt.excluded.expected_five_year_inflation,
                "expectations_index": stmt.excluded.expectations_index
            }
        )

        try:
            with get_session() as session:
                result = session.exec(stmt)
                session.commit()
                return result
        except Exception as e:
            print(f"Ошибка при обновлении эмитентов: {e}")
            raise

    def inflation_data_update(self, data: list[dict[str, Any]]):
        stmt = insert(InflationData).values(data)

        stmt = stmt.on_conflict_do_update(
            index_elements=[InflationData.record_date],
            set_={
                "trend_inflation_3y":  stmt.excluded.trend_inflation_3y,
                "trend_inflation_5y":  stmt.excluded.trend_inflation_5y,
                "modified_core_inflation":  stmt.excluded.modified_core_inflation
            }
        )

        try:
            with get_session() as session:
                result = session.exec(stmt)
                session.commit()
                return result
        except Exception as e:
            print(f"Ошибка при обновлении эмитентов: {e}")
            raise

    def inflation_data_select(
            self, data: Optional[dict[str, date]] = None
    ) -> list[InflationExpectations]:

        stmt = select(InflationExpectations)
        if data is not None:
            if data.get("from_date") is not None:
                stmt = stmt.where(InflationExpectations.recorddata >= data["from_date"])

            if data.get("till_date") is not None:
                stmt = stmt.where(InflationExpectations.recorddata <= data["till_date"])

        stmt = stmt.order_by(InflationExpectations.recorddata)
        try:
            with get_session() as session:
                result = session.exec(stmt).scalars().all()
                print(type(result))
                print(type(result[0]) if result else "Пустой результат")
                return result
        except Exception as e:
            print(f"Ошибка при обновлении эмитентов: {e}")
            raise

inflation_repository: Optional[InflationRepository] = None

def get_inflation_repository():
    global inflation_repository

    if inflation_repository is None:
        inflation_repository = InflationRepository()

    return inflation_repository