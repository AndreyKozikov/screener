from typing import Optional
from db_repository.models.inflations import InflationExpectations
from sqlalchemy.dialects.sqlite import insert
from db_repository.core.database_init import get_session


class InflationRepository:

    def __init__(self):
        pass

    def inflation_expectations_update(self, data: list[InflationExpectations]):
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

inflation_repository: Optional[InflationRepository] = None

def get_inflation_repository():
    global inflation_repository

    if inflation_repository is None:
        inflation_repository = InflationRepository()

    return inflation_repository