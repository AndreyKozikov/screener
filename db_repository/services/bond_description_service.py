"""Application service for updating MOEX bond descriptions."""

from typing import Any

from db_repository.repository.bond_description_repository import BondDescriptionRepository


class BondDescriptionService:
    def __init__(self) -> None:
        self.repository = BondDescriptionRepository()

    def update(self, descriptions: dict[str, dict[str, Any]]) -> dict[str, Any]:
        return self.repository.upsert_by_secid(descriptions)


_bond_description_service: BondDescriptionService | None = None


def get_bond_description_service() -> BondDescriptionService:
    global _bond_description_service
    if _bond_description_service is None:
        _bond_description_service = BondDescriptionService()
    return _bond_description_service
