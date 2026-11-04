"""Роутеры для работы с облигациями и купонами.

Этот модуль содержит роутеры FastAPI для обработки HTTP запросов, связанных
с облигациями и купонами. Включает endpoints для получения списка облигаций,
детальной информации об облигациях и данных о купонах.
"""

import asyncio

from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional
from app.models import (
    BondDetail,
    BondFilters,
    BondYieldRuoniaChartResponse,
    BondsListResponse,
    Coupon,
    CouponsBySecid,
    CouponsListResponse,
    MultipleCouponsResponse,
    BondPriceHistoryResponse,
)
from app.models.schemasDTO.bond_float_params_dto import BondFloatParamsDTO
from app.models.schemasDTO.bonds_list_filters_dto import BondsListFiltersDTO
from app.services.bond_float_params_service import BondFloatParamsService
from app.services.coupon_service import get_coupon_service
from app.services.bonds_service import (
    get_bond_detail,
    get_bonds_list,
)
from app.services.bond_ruonia_chart_service import get_yield_ruonia_chart_data
from app.services.trading_history_service import get_trading_history_service
from app.repository.db.bonds_repository import BondsRepository
from app.repository.db.bond_float_params_repository import BondFloatParamsRepository

router = APIRouter(prefix="/api/bonds", tags=["bonds"])
"""Роутер FastAPI для обработки запросов к API облигаций."""


def get_bond_float_params_service() -> BondFloatParamsService:
    """Фабрика зависимости для BondFloatParamsService."""
    bonds_repo = BondsRepository()
    float_repo = BondFloatParamsRepository()
    return BondFloatParamsService(bonds_repo=bonds_repo, float_repo=float_repo)


@router.post("/", response_model=BondsListResponse)  # Переведен на внешний сервис
async def list_bonds(payload: BondsListFiltersDTO):

    data = payload.model_dump(exclude_none=True)

    filters = BondFilters(**data)

    result = await get_bonds_list(
        filters=filters,
        emitent_title = data.get("emitent_title", None),
        exclude_spob=data.get("exclude_spob", False)
    )
    return result


@router.get("/coupons/batch", response_model=MultipleCouponsResponse)
async def get_bonds_coupons_batch(secids: List[str] = Query(..., min_length=1)):
    clean_secids = list(dict.fromkeys(item.strip() for item in secids if item and item.strip()))
    if not clean_secids:
        raise HTTPException(status_code=400, detail="At least one valid secid is required")
    batch = await asyncio.to_thread(get_coupon_service().get_coupons_batch, clean_secids)
    return MultipleCouponsResponse(data=[
        CouponsBySecid(
            secid=secid,
            coupons=[Coupon(**item) for item in batch.get(secid, {}).get("coupons", [])],
        )
        for secid in clean_secids
    ])


@router.get("/{secid}/coupons", response_model=CouponsListResponse)
async def get_bond_coupons(
    secid: str,
    secids: Optional[List[str]] = Query(None),
) -> CouponsListResponse:
    service = get_coupon_service()
    if secids:
        clean_secids = list(dict.fromkeys(item.strip() for item in secids if item and item.strip()))
        if not clean_secids:
            raise HTTPException(status_code=400, detail="At least one valid secid is required")
        target = secid if secid in clean_secids else clean_secids[0]
        batch = await asyncio.to_thread(service.get_coupons_batch, clean_secids)
        coupons = batch.get(target, {}).get("coupons", [])
    else:
        try:
            data = await asyncio.to_thread(service.get_coupons, secid)
            coupons = data.get("coupons", [])
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Failed to get coupons: {exc}") from exc
    return CouponsListResponse(coupons=[Coupon(**item) for item in coupons])


@router.get("/float-params/secids", response_model=List[str])
async def get_floater_secids_from_params(
        service: BondFloatParamsService = Depends(get_bond_float_params_service),
):
    """Возвращает список SECID облигаций, для которых найдены параметры флоатера.

    Фильтрует записи bond_float_params по условию is_find != 0 и маппит
    bond_id в SECID.

    Returns:
        Список SECID облигаций с найденными параметрами флоатера.
    """
    return await asyncio.to_thread(service.get_floater_secids_from_params)


@router.get("/{secid}/yield-ruonia-chart", response_model=BondYieldRuoniaChartResponse)
async def get_bond_yield_ruonia_chart(secid: str):
    """Возвращает нормализованные данные для графика сравнения доходности облигации и RUONIA.

    Период: от (текущая дата минус 1 день) на год назад. В ответ входят только даты,
    по которым есть и ставка RUONIA, и доходность к погашению (yieldatwap) облигации.

    Args:
        secid: Идентификатор облигации (SECID).

    Returns:
        BondYieldRuoniaChartResponse с полем data — список точек (date, ruonia_rate, yieldatwap).
    """
    result = await asyncio.to_thread(get_yield_ruonia_chart_data, secid)
    return result


@router.get("/{secid}/price-history", response_model=BondPriceHistoryResponse)
async def get_bond_price_history(secid: str):
    """Возвращает историю цен (tradedate, open) для построения графика.

    Данные берутся из таблицы bond_trading_history.

    Args:
        secid: Идентификатор облигации (SECID).

    Returns:
        BondPriceHistoryResponse с полем data — список точек (date, open).
    """
    try:
        svc = get_trading_history_service()
    except RuntimeError as e:
        raise HTTPException(
            status_code=503,
            detail="Сервис истории торгов не инициализирован.",
        ) from e

    data = await asyncio.to_thread(svc.get_price_history, secid)
    return BondPriceHistoryResponse(secid=secid, data=data)


@router.get("/{secid}/float-params", response_model=BondFloatParamsDTO)
async def get_bond_float_params(
        secid: str,
        service: BondFloatParamsService = Depends(get_bond_float_params_service),
):
    """Возвращает параметры плавающей ставки облигации по SECID.

    Args:
        secid: Идентификатор ценной бумаги (SECID).

    Returns:
        BondFloatParamsDTO с параметрами флоатера и данными облигации.

    Raises:
        HTTPException: Если облигация не найдена, параметры флоатера отсутствуют
            или is_find == 0 (статус 404).
    """
    dto = await asyncio.to_thread(service.get_float_params_by_secid, secid)
    if dto is None:
        raise HTTPException(
            status_code=404,
            detail=f"Float params not found for bond {secid}",
        )
    return dto


@router.get("/{secid}", response_model=BondDetail)
async def get_bond_details(secid: str):
    """Получает детальную информацию об облигации по SECID.

    Загружает данные из БД (Bond, BondSecurity, BondMarketData), преобразует
    в BondDetailDTO и возвращает.

    Args:
        secid: Идентификатор облигации (SECID) для получения детальной информации.

    Returns:
        Объект BondDetail (BondDetailDTO) с полными данными об облигации:
        - securities: Данные секции securities (UPPERCASE ключи)
        - marketdata: Данные секции marketdata или None
        - marketdata_yields: Список данных секции marketdata_yields

    Raises:
        HTTPException: Если облигация с указанным SECID не найдена (статус 404).
    """
    dto = await asyncio.to_thread(get_bond_detail, secid)
    if dto is None:
        raise HTTPException(status_code=404, detail=f"Bond {secid} not found")
    return BondDetail(
        securities=dto.securities,
        marketdata=dto.marketdata,
        marketdata_yields=dto.marketdata_yields,
        emitent_inn=dto.emitent_inn,
    )
