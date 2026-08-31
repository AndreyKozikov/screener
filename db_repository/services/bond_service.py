from typing import List, Optional, Dict, Any

from db_repository.models.bond import BondSecurity, BondMarketData, BondMarketDataYield, Bond
from db_repository.models.bonds_data_dto import BondsDataDTO
from db_repository.repository.bond_repository import get_db_repository
from db_repository.models.bonds_filters_dto import BondsListFiltersDTO
from db_repository.models.bond_filters import BondFilters
from db_repository.models.bond_response_dto import BondResponseDTO
from db_repository.models.coupon_response_dto import CouponResponseDTO

from collections import defaultdict


class BondService:

    def __init__(self):
        self.db_repository = get_db_repository()

    async def get_bonds_list(
            self,
            data: BondsListFiltersDTO
    ) -> List[BondResponseDTO]:

        bond_filters_data = data.model_dump(exclude_none=True, exclude={'emitent_title', 'exclude_spob'})
        bond_filters = BondFilters(**bond_filters_data)
        emitent_title = data.emitent_title
        exclude_spob = data.exclude_spob

        # Выборка через SQLModel API; возвращаются объекты Bond
        try:
            bond_rows, coupon_rows = self.db_repository.select(filters=bond_filters, exclude_spob=exclude_spob)
        except Exception as e:
            if "no such table" in str(e).lower():
                bond_rows = []
            else:
                raise
        coupons_map = defaultdict(list)

        for coupon in coupon_rows:
            coupons_map[coupon.bond_id].append(coupon)

        result = [
            BondResponseDTO(
                **bond.__dict__,
                coupons=[
                    CouponResponseDTO(**coupon.__dict__)
                    for coupon in coupons_map.get(bond.id, [])
                ]
            )
            for bond in bond_rows
        ]

        return result

    async def bond_counts(self, exclude_spob: bool = False) -> int:
        try:
            bond_counts = self.db_repository.count_bonds(exclude_spob=exclude_spob)
            return bond_counts
        except Exception as e:
            raise

    async def get_bond_details(self, secid: str):
        try:
            bond_detail = await self.db_repository.bond_details(secid)
        except Exception as e:
            raise
        return BondResponseDTO.model_validate(bond_detail, from_attributes=True)

    async def bonds_data_update(self, data: BondsDataDTO):

        bonds = []
        securities = []
        marketdata = []
        marketdata_yields = []

        for secid, bond_data in data.root.items():

            security = BondSecurity.model_validate(bond_data.securities)

            marketdata_item = BondMarketData.model_validate(bond_data.marketdata)

            marketdata_yield = BondMarketDataYield.model_validate(bond_data.marketdata_yields)

            bond_source = {
                **bond_data.securities,
                **bond_data.marketdata,
                **bond_data.marketdata_yields
            }

            bond = Bond.model_validate(bond_source)

            bonds.append(
                self._model_to_dict(
                    bond,
                    exclude={"id"}
                )
            )
            securities.append(
                self._model_to_dict(
                    security,
                    exclude={"id", "bond_id"},
                    extra={"secid": secid},
                )
            )

            marketdata.append(
                self._model_to_dict(
                    marketdata_item,
                    exclude={"id", "bond_id"},
                    extra={"secid": secid},
                )
            )

            marketdata_yields.append(
                self._model_to_dict(
                    marketdata_yield,
                    exclude={"id", "bond_id"},
                    extra={"secid": secid},
                )
            )

        return {
            "bonds": bonds,
            "securities": securities,
            "marketdata": marketdata,
            "marketdata_yields": marketdata_yields,
        }

    async def get_all_secids(self)-> List[str]:
        secids = []
        result = await self.db_repository.get_all_secids()
        return result

    @staticmethod
    def _model_to_dict(
            model,
            exclude: set[str] | None,
            extra: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        exclude = exclude or set()

        result = {
            column.name: getattr(model, column.name)
            for column in model.__table__.columns
            if column.name not in exclude
        }

        if extra:
            result.update(extra)

        return result


bond_service: Optional[BondService] = None


def get_bond_service() -> BondService:
    global bond_service
    if bond_service is None:
        bond_service = BondService()
    return bond_service
