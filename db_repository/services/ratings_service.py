from db_repository.repository.ratings_repository import get_ratings_repository
from typing import List, Optional
from db_repository.models.ratings import BondRatingBase, EmitentRatingBase


class RatingsService:

    def __init__(self):
        self.db_ratings_repository = get_ratings_repository()

    async def get_bond_ratings(
            self,
            bondids: List[int],
    ) -> List[BondRatingBase]:
        result = await self.db_ratings_repository.get_bond_ratings(bondids)
        bonds_rating = [
            BondRatingBase.model_validate(rating)
            for rating in result
        ]
        return bonds_rating

    async def get_emitent_ratings(
            self,
            emitent_ids: List[int],
    ) -> List[EmitentRatingBase]:
        result = await self.db_ratings_repository.get_emitent_ratings(emitent_ids)
        emitents_rating = [
            EmitentRatingBase.model_validate(rating)
            for rating in result
        ]
        return emitents_rating

    async def get_bonds_rating_map(self):
        rows = await self.db_ratings_repository.get_bonds_rating_map()
        return [list(row) for row in rows]

    async def get_emitents_rating_map(self):
        rows = await self.db_ratings_repository.get_emitents_rating_map()
        return [list(row) for row in rows]


coupon_service: Optional[RatingsService] = None

def get_ratings_service():
    global coupon_service
    if coupon_service is None:
        coupon_service = RatingsService()
    return coupon_service