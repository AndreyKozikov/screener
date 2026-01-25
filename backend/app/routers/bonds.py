import asyncio

from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
from datetime import date

from app.models.bond import BondDetail
from app.models.filters import BondFilters
from app.models.responses import BondsListResponse
from app.models.coupons import BondCouponsResponse, CouponsListResponse, MultipleCouponsResponse, CouponsBySecid
from app.services.data_loader import get_data_loader
from app.services.bonds_service import get_bonds_list
from app.services.coupon_service import get_coupon_service
from app.services.db_orchestrator import DBOrchestrator
from app.config import settings
from app.utils.logger import get_data_update_logger

router = APIRouter(prefix="/api/bonds", tags=["bonds"])


@router.get("/", response_model=BondsListResponse)
async def list_bonds(
    coupon_min: Optional[float] = Query(None, ge=0, le=100),
    coupon_max: Optional[float] = Query(None, ge=0, le=100),
    yield_min: Optional[float] = Query(None, ge=0, le=100),
    yield_max: Optional[float] = Query(None, ge=0, le=100),
    coupon_yield_min: Optional[float] = Query(None, ge=0, le=100),
    coupon_yield_max: Optional[float] = Query(None, ge=0, le=100),
    matdate_from: Optional[date] = Query(None),
    matdate_to: Optional[date] = Query(None),
    listlevel: Optional[List[int]] = Query(None),
    faceunit: Optional[List[str]] = Query(None),
    bondtype: Optional[List[int]] = Query(None, description="Bond type IDs (from bond_type_mapping: 1=exchange_bond, 2=ofz_bond, etc.)"),
    bondtype43: Optional[List[int]] = Query(None, description="Bond type43 IDs (from bond_type43_mapping: 1=Амортизируемые облигации, 6=Фикс с известным купоном, etc.)"),
    rating_min: Optional[str] = Query(None),
    rating_max: Optional[str] = Query(None),
    emitent_title: Optional[str] = Query(None, description="Filter by emitent title"),
    exclude_spob: Optional[bool] = Query(False, description="Exclude bonds with trading mode SPOB"),
):
    """
    Выгрузка списка облигаций с фильтрами (чистая архитектура).

    Роутер: валидирует query-параметры, вызывает сервисный слой, возвращает JSON.
    Сервис: вызывает DBBonds.select() для получения данных с применением всех фильтров
    на уровне БД, преобразует данные в формат для фронта, применяет фильтр по эмитенту
    (если указан). Поиск (search) выполняется на клиенте.

    Вся фильтрация облигаций (кроме фильтрации по эмитенту) выполняется в методе
    DBBonds.select() на уровне SQL для повышения производительности.

    Фильтры: coupon, yield, coupon_yield, matdate, listlevel, faceunit,
    bondtype (ID), bondtype43 (ID), rating_min/max, emitent_title, exclude_spob.
    """
    filters = BondFilters(
        coupon_min=coupon_min,
        coupon_max=coupon_max,
        yield_min=yield_min,
        yield_max=yield_max,
        coupon_yield_min=coupon_yield_min,
        coupon_yield_max=coupon_yield_max,
        matdate_from=matdate_from,
        matdate_to=matdate_to,
        listlevel=listlevel,
        faceunit=faceunit,
        bondtype=bondtype,
        bondtype43=bondtype43,
        rating_min=rating_min,
        rating_max=rating_max,
        search=None,
        skip=0,
        limit=1000,
    )
    result = await asyncio.to_thread(
        get_bonds_list,
        filters,
        emitent_title=emitent_title,
        exclude_spob=bool(exclude_spob),
    )
    return result

@router.post("/refresh")
async def refresh_bonds_data():
    """
    Download the latest bonds dataset from MOEX and refresh cached data.
    Also clears metadata cache (columns and descriptions) to ensure fresh data.
    """
    logger = get_data_update_logger()
    logger.info(f"[API /bonds/refresh] Received request to refresh bonds data from {settings.MOEX_BONDS_URL}")
    
    loader = get_data_loader()
    
    try:
        summary = await asyncio.to_thread(
            loader.refresh_bonds_dataset,
            settings.MOEX_BONDS_URL,
        )
        logger.info(f"[API /bonds/refresh] Bonds dataset refresh completed successfully: {summary}")
        
        # Update database table structure and data after successful file save
        orchestrator = DBOrchestrator()
        db_refresh_result = await asyncio.to_thread(orchestrator.migrate, "bonds")
        if db_refresh_result:
            logger.info("[API /bonds/refresh] Database table bonds refreshed successfully")
        else:
            logger.warning("[API /bonds/refresh] Database table bonds refresh failed, but bonds.json was saved successfully")
        
        # Also clear metadata cache to ensure columns and descriptions are reloaded
        loader.clear_metadata_cache()
        logger.info("[API /bonds/refresh] Metadata cache cleared")
    except RuntimeError as exc:
        logger.error(f"[API /bonds/refresh] Failed to refresh bonds data: {exc}")
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    
    result = {
        "status": "ok",
        "updated": summary,
        "source": settings.MOEX_BONDS_URL,
        "metadata_cache_cleared": True,
    }
    logger.info(f"[API /bonds/refresh] Returning success response: {result}")
    return result


@router.get("/{secid}", response_model=BondDetail)
async def get_bond_detail(secid: str):
    """
    Get detailed information for a specific bond by SECID.
    
    Returns complete bond data including securities, marketdata, and yields.
    """
    loader = get_data_loader()
    details = await loader.get_bond_details()
    
    if secid not in details:
        raise HTTPException(status_code=404, detail=f"Bond {secid} not found")
    
    bond_data = details[secid]
    return BondDetail(**bond_data)


@router.post("/refresh-coupons")
async def refresh_coupons_data(force_refresh: bool = Query(False, description="Force refresh all coupons, ignoring cache (last_updated date)")):
    """
    Refresh coupons data for all bonds from bonds.json file.
    
    Reads SECID from bonds.json and updates coupon data for each bond
    by fetching from MOEX API. All processing is done on the backend.
    
    Args:
        force_refresh: If True, force refresh all coupons regardless of cache (ignore last_updated date).
                      If False, only refresh coupons that are stale (older than 14 days).
    
    Returns:
        Dictionary with refresh statistics: total, updated, errors, skipped
    """
    logger = get_data_update_logger()
    if force_refresh:
        logger.info("[API /bonds/refresh-coupons] Received request to refresh coupons data (FORCE REFRESH - ignoring cache)")
        print(f"[КУПОНЫ] Начало принудительного обновления купонов для всех облигаций (игнорируется кэш)")
    else:
        logger.info("[API /bonds/refresh-coupons] Received request to refresh coupons data (only stale data will be refreshed)")
        print(f"[КУПОНЫ] Начало обновления купонов для всех облигаций (только устаревшие данные)")
    
    try:
        coupon_service = get_coupon_service()
        data_loader = get_data_loader()
        
        # Get all bonds data
        logger.info("[API /bonds/refresh-coupons] Loading bonds data...")
        print(f"[КУПОНЫ] Загрузка списка облигаций...")
        bonds_list = await data_loader.get_bonds()
        bonds_count = len(bonds_list)
        logger.info(f"[API /bonds/refresh-coupons] Found {bonds_count} bonds to process")
        print(f"[КУПОНЫ] Найдено облигаций для обработки: {bonds_count}")
        
        # Statistics
        updated_count = 0
        error_count = 0
        skipped_count = 0
        
        # Process each bond
        print(f"[КУПОНЫ] Начало обработки облигаций...")
        print(f"{'='*80}")
        
        for idx, bond in enumerate(bonds_list):
            secid = bond.SECID
            
            if not secid:
                logger.warning(f"[API /bonds/refresh-coupons] Bond {idx + 1}/{bonds_count}: Skipping - missing SECID")
                print(f"[КУПОНЫ] [{idx + 1}/{bonds_count}] ПРОПУЩЕНО: отсутствует SECID")
                skipped_count += 1
                continue
            
            # Log progress for every bond
            progress_percent = ((idx + 1) / bonds_count) * 100
            print(f"[КУПОНЫ] [{idx + 1}/{bonds_count}] ({progress_percent:.1f}%) Обработка облигации: SECID={secid}")
            
            if (idx + 1) % 100 == 0:
                logger.info(f"[API /bonds/refresh-coupons] Processing bond {idx + 1}/{bonds_count}: SECID={secid}")
                print(f"[КУПОНЫ] Прогресс: обработано {idx + 1} из {bonds_count} облигаций")
            
            try:
                # Get coupons with force_refresh parameter
                # If force_refresh=True, always fetch from MOEX
                # If force_refresh=False, get_coupons will check if data is stale (older than 14 days)
                await asyncio.to_thread(
                    coupon_service.get_coupons,
                    secid,
                    force_refresh  # Use the parameter from request
                )
                updated_count += 1
                print(f"[КУПОНЫ] [{idx + 1}/{bonds_count}] ✓ Успешно обновлено: SECID={secid}")
            except Exception as exc:
                error_type = type(exc).__name__
                error_msg = str(exc)
                logger.error(f"[API /bonds/refresh-coupons] ERROR: Failed to update coupons for {secid} - {error_type}: {error_msg}")
                print(f"[КУПОНЫ] [{idx + 1}/{bonds_count}] ✗ ОШИБКА при обновлении SECID={secid}: {error_type} - {error_msg}")
                error_count += 1
                # Continue processing other bonds even if one fails
                continue
        
        print(f"{'='*80}")
        summary = {
            "status": "ok",
            "total_bonds": bonds_count,
            "updated": updated_count,
            "errors": error_count,
            "skipped": skipped_count
        }
        
        logger.info(f"[API /bonds/refresh-coupons] Refresh completed: total={bonds_count}, updated={updated_count}, errors={error_count}, skipped={skipped_count}")
        print(f"[КУПОНЫ] Обновление завершено!")
        print(f"[КУПОНЫ] Всего облигаций: {bonds_count}")
        print(f"[КУПОНЫ] Успешно обновлено: {updated_count}")
        print(f"[КУПОНЫ] Ошибок: {error_count}")
        print(f"[КУПОНЫ] Пропущено: {skipped_count}")
        print(f"{'='*80}\n")
        
        # Update database table structure and data after successful file save
        logger.info("[API /bonds/refresh-coupons] Starting database synchronization...")
        print(f"[КУПОНЫ] Начало синхронизации с базой данных...")
        orchestrator = DBOrchestrator()
        db_refresh_result = await asyncio.to_thread(orchestrator.migrate, "coupons")
        if db_refresh_result:
            logger.info("[API /bonds/refresh-coupons] Database table coupons refreshed successfully")
            print(f"[КУПОНЫ] Таблица coupons успешно обновлена в базе данных")
        else:
            logger.warning("[API /bonds/refresh-coupons] Database table coupons refresh failed, but coupons_data.json was saved successfully")
            print(f"[КУПОНЫ] ВНИМАНИЕ: Обновление таблицы coupons в БД завершилось с ошибкой, но файл coupons_data.json сохранён успешно")
        
        return summary
        
    except Exception as exc:
        error_type = type(exc).__name__
        error_msg = str(exc)
        logger.error(f"[API /bonds/refresh-coupons] ERROR: {error_type} - {error_msg}")
        print(f"[КУПОНЫ] КРИТИЧЕСКАЯ ОШИБКА: {error_type} - {error_msg}")
        print(f"{'='*80}\n")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to refresh coupons: {error_msg}"
        ) from exc


@router.get("/{secid}/coupons", response_model=CouponsListResponse)
async def get_bond_coupons(
    secid: str,
    secids: Optional[List[str]] = Query(None, description="List of secids for batch request (alternative to path parameter)"),
    force_refresh: bool = Query(False, description="Force refresh from MOEX API")
):
    """
    Get coupon payments data for one or multiple bonds by SECID.
    
    Supports two modes:
    1. Single bond: Use path parameter `{secid}` (e.g., /api/bonds/RU000A0ZZYQ2/coupons)
    2. Multiple bonds: Use query parameter `secids` (e.g., /api/bonds/any/coupons?secids=RU000A0ZZYQ2&secids=RU000A0ZZYQ3)
    
    When `secids` query parameter is provided, it takes precedence over path parameter.
    Returns list of coupons with coupondate, value (sum), and valueprc (rate).
    If data is missing or older than 14 days, automatically downloads from MOEX API.
    """
    try:
        coupon_service = get_coupon_service()
        
        # If secids query parameter is provided, use batch mode
        if secids and len(secids) > 0:
            # Validate secids list
            if not all(isinstance(s, str) and s.strip() for s in secids):
                raise HTTPException(
                    status_code=400,
                    detail="All secids must be non-empty strings"
                )
            
            # Remove duplicates and empty strings
            unique_secids = list(dict.fromkeys([s.strip() for s in secids if s and s.strip()]))
            
            if not unique_secids:
                raise HTTPException(
                    status_code=400,
                    detail="At least one valid secid is required"
                )
            
            # Get coupons for multiple bonds
            batch_data = await asyncio.to_thread(
                coupon_service.get_coupons_batch,
                unique_secids,
                use_db=True
            )
            
            # For backward compatibility with single bond requests, return first bond's data
            # But if multiple secids were requested, we should return MultipleCouponsResponse
            # However, to maintain backward compatibility, we'll return the first one
            # The frontend should use a separate endpoint or we can add a new endpoint
            # For now, let's return the first secid's data (or the path secid if it's in the list)
            target_secid = secid if secid in unique_secids else unique_secids[0]
            
            if target_secid not in batch_data:
                raise HTTPException(
                    status_code=404,
                    detail=f"No coupon data found for {target_secid}"
                )
            
            bond_data = batch_data[target_secid]
            coupons_data = bond_data.get("coupons", [])
            coupon_type = bond_data.get("coupon_type")
            
            # Convert dicts to Coupon models
            from app.models.coupons import Coupon
            coupons = [Coupon(**coupon) for coupon in coupons_data]
            
            return CouponsListResponse(coupons=coupons, coupon_type=coupon_type)
        
        # Single bond mode: use path parameter
        # Get full coupon data to access amortizations with coupon_type
        full_coupon_data = await asyncio.to_thread(
            coupon_service.get_coupons,
            secid,
            force_refresh
        )
        
        # Extract coupons and coupon_type
        coupons_data = full_coupon_data.get("coupons", [])
        amortizations = full_coupon_data.get("amortizations", [])
        
        # Get coupon_type from amortizations (all amortizations have the same coupon_type)
        coupon_type = None
        if amortizations and len(amortizations) > 0:
            coupon_type = amortizations[0].get("coupon_type")
        
        # Convert dicts to Coupon models
        from app.models.coupons import Coupon
        coupons = [Coupon(**coupon) for coupon in coupons_data]
        
        return CouponsListResponse(coupons=coupons, coupon_type=coupon_type)
    except HTTPException:
        raise
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to get coupons: {str(exc)}") from exc


@router.get("/coupons/batch", response_model=MultipleCouponsResponse)
async def get_bonds_coupons_batch(
    secids: List[str] = Query(..., description="List of secids for batch request", min_length=1)
):
    """
    Get coupon payments data for multiple bonds by SECID list.
    
    Returns coupons grouped by secid. Each entry contains:
    - secid: Security ID
    - coupons: List of coupon payments
    - coupon_type: FIX or FLOAT (if available)
    
    Example: /api/bonds/coupons/batch?secids=RU000A0ZZYQ2&secids=RU000A0ZZYQ3
    """
    try:
        # Validate secids list
        if not all(isinstance(s, str) and s.strip() for s in secids):
            raise HTTPException(
                status_code=400,
                detail="All secids must be non-empty strings"
            )
        
        # Remove duplicates and empty strings
        unique_secids = list(dict.fromkeys([s.strip() for s in secids if s and s.strip()]))
        
        if not unique_secids:
            raise HTTPException(
                status_code=400,
                detail="At least one valid secid is required"
            )
        
        coupon_service = get_coupon_service()
        
        # Get coupons for multiple bonds
        batch_data = await asyncio.to_thread(
            coupon_service.get_coupons_batch,
            unique_secids,
            use_db=True
        )
        
        # Convert to response model
        from app.models.coupons import Coupon
        result_data = []
        
        for secid in unique_secids:
            if secid in batch_data:
                bond_data = batch_data[secid]
                coupons_data = bond_data.get("coupons", [])
                coupon_type = bond_data.get("coupon_type")
                
                # Convert dicts to Coupon models
                coupons = [Coupon(**coupon) for coupon in coupons_data]
                
                result_data.append(CouponsBySecid(
                    secid=secid,
                    coupons=coupons,
                    coupon_type=coupon_type
                ))
            else:
                # Return empty coupons for missing secids
                result_data.append(CouponsBySecid(
                    secid=secid,
                    coupons=[],
                    coupon_type=None
                ))
        
        return MultipleCouponsResponse(data=result_data)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to get coupons batch: {str(exc)}") from exc
