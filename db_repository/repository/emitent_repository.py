from db_repository.core.database_init import get_session
from typing import Optional
from sqlalchemy.dialects.sqlite import insert
from sqlmodel import select, delete
from db_repository.models.emitent import Emitent
from db_repository.models.bond_emitent import BondEmitent

class EmitentRepository:

    def __init__(self):
        pass


    def update_emitents(self, emitents, reset: bool = False):

        stmt = insert(Emitent).values(emitents)

        stmt = stmt.on_conflict_do_update(
            index_elements=[Emitent.moex_id],
            set_={
                "moex_id": stmt.excluded.moex_id,
                "okpo": stmt.excluded.okpo,
                "title": stmt.excluded.title,
                "type": stmt.excluded.type,
            },
        )

        try:
            with get_session() as session:
                result = session.exec(stmt)
                session.commit()
                return result
        except Exception as e:
            print(f"Ошибка при обновлении эмитентов: {e}")
            raise

    def get_emitents_ids(self, inns: set[str]):
        stmt = (
            select(Emitent.inn, Emitent.id)
            .where(Emitent.inn.in_(inns))
        )

        with get_session() as session:
            result = session.exec(stmt).all()
            return result

    def update_emitent_ids_to_bond(self, data: dict[str, int]):
        stmt = insert(BondEmitent).values(data)

        stmt = stmt.on_conflict_do_update(
            index_elements=[BondEmitent.secid],
            set_={
                "emitent_id": stmt.excluded.emitent_id,
            },
        )
        try:
            with get_session() as session:
                result = session.exec(stmt)
                session.commit()
                return result
        except:
            raise

    def delete_emitents(self):
        with get_session() as session:
            session.exec(delete(Emitent))
            session.commit()

emitent_repository: Optional[EmitentRepository] = None

def get_emitent_repository():
    global emitent_repository
    if emitent_repository is None:
        emitent_repository = EmitentRepository()
    return emitent_repository