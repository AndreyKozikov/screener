from typing import Any, Optional
from db_repository.core.database_init import get_session
from sqlalchemy.dialects.sqlite import insert
from db_repository.models.ipc import Ipc, IpcWeekly


class IpcRepository:

    def __init__(self):
        pass


    def update_ipc_data(self, data: list[dict[str, Any]]):
        stmt = insert(Ipc).values(data)

        stmt = stmt.on_conflict_do_update(
            index_elements=[Ipc.record_data],
            set_={
                "ipc": stmt.excluded.ipc,
                "food_ipc": stmt.excluded.food_ipc,
                "non_food_ipc": stmt.excluded.non_food_ipc,
                "services_ipc": stmt.excluded.services_ipc,
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

    def ipc_weekly_update(self, data: list[dict[str, Any]]):
        stmt = insert(IpcWeekly).values(data)

        stmt = stmt.on_conflict_do_update(
            index_elements=[IpcWeekly.start_date],
            set_={
                "end_date": stmt.excluded.end_date,
                "ipc_weekly": stmt.excluded.ipc_weekly
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


ipc_repository: Optional[IpcRepository] = None

def get_ipc_repository():
    global ipc_repository

    if ipc_repository is None:
        ipc_repository = IpcRepository()

    return ipc_repository