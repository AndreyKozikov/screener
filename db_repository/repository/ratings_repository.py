from db_repository.core.database_init import get_session
from typing import Optional, Any
from typing import List
from sqlmodel import select
from db_repository.models.ratings import BondRating, EmitentRating, RatingAgency
from db_repository.models.bond_emitent import BondEmitent
from db_repository.models.bond import Bond
from db_repository.models.emitent import Emitent
from sqlalchemy.dialects.sqlite import insert

class RatingRepository:
    def __init__(selfself):
        pass


    async def get_bond_ratings(self, bondids: List[int]):
        statement = (
            select(BondRating)
            .where(BondRating.bond_id.in_(bondids))
        )

        try:
            with get_session() as session:
                result = session.exec(statement).fetchall()

                return result
        except:
            raise

    async def get_emitent_ratings(self, emitent_ids: List[int]):
        statement = (
            select(EmitentRating)
            .where(EmitentRating.emitent_id.in_(emitent_ids))
        )

        try:
            with get_session() as session:
                result = session.exec(statement).fetchall()
                return result
        except:
            raise

    async def get_bonds_rating_map(self):
        statement = (
            select(Bond.secid, RatingAgency.agency_name_short_ru, BondRating.rating_level_name)
            .join(BondRating, Bond.id == BondRating.bond_id)
            .join(RatingAgency, BondRating.agency_id == RatingAgency.agency_id)
        )
        try:
            with get_session() as session:
                result = session.exec(statement).fetchall()
                return result
        except:
            raise

    async def get_emitents_rating_map(self):
        statement = (
            select(
                Bond.secid,
                Emitent.type,
                RatingAgency.agency_name_short_ru,
                EmitentRating.rating_level_name,
            )
            .join(BondEmitent, BondEmitent.secid == Bond.secid)
            .join(Emitent, BondEmitent.emitent_id == Emitent.id)
            .join(EmitentRating, EmitentRating.emitent_id == Emitent.id)
            .join(RatingAgency, EmitentRating.agency_id == RatingAgency.id)
        )
        try:
            with get_session() as session:
                result = session.exec(statement).fetchall()
                return result
        except:
            raise

    def update_emitents_rating(self, data: list[dict[str, Any]]):
        stmt = insert(EmitentRating).values(data)

        stmt = stmt.on_conflict_do_update(
            index_elements=[
                EmitentRating.emitent_id,
                EmitentRating.agency_id,
            ],
            set_={
                "rating_level_name": stmt.excluded.rating_level_name,
                "rating_date": stmt.excluded.rating_date,
                "rating_publicate_date": stmt.excluded.rating_publicate_date,
            },
        )
        try:
            with get_session() as session:
                result = session.exec(stmt)
                session.commit()
                return result
        except:
            raise



ratings_repository: Optional[RatingRepository] = None

def get_ratings_repository() -> RatingRepository:
    global ratings_repository
    if ratings_repository is None:
        ratings_repository = RatingRepository()
    return ratings_repository
