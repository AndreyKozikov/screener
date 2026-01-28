"""Роутеры для работы с облигациями и купонами.

Этот модуль содержит роутеры FastAPI для обработки HTTP запросов, связанных
с облигациями и купонами. Включает endpoints для получения списка облигаций,
детальной информации об облигациях, данных о купонах и обновления данных.
"""

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
from app.repository.db_orchestrator import DBOrchestrator
from app.config import settings
from app.utils.logger import get_data_update_logger

router = APIRouter(prefix="/api/bonds", tags=["bonds"])
"""Роутер FastAPI для обработки запросов к API облигаций."""




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
    """Получает список облигаций с применением фильтров.
    
    Роутер валидирует query-параметры, вызывает сервисный слой и возвращает JSON
    с отфильтрованным списком облигаций. Сервис вызывает BondsRepository.select() для
    получения данных с применением всех фильтров на уровне БД, преобразует данные
    в формат для фронтенда и применяет фильтр по эмитенту (если указан).
    
    Args:
        coupon_min: Минимальный процент купона (0-100).
        coupon_max: Максимальный процент купона (0-100).
        yield_min: Минимальная доходность к погашению (0-100).
        yield_max: Максимальная доходность к погашению (0-100).
        coupon_yield_min: Минимальная доходность купона к цене (0-100).
        coupon_yield_max: Максимальная доходность купона к цене (0-100).
        matdate_from: Начальная дата погашения (включительно).
        matdate_to: Конечная дата погашения (включительно).
        listlevel: Список уровней листинга для фильтрации.
        faceunit: Список валют для фильтрации (например, ["SUR", "USD"]).
        bondtype: Список ID типов облигаций из bond_type_mapping
            (1=exchange_bond, 2=ofz_bond, и т.д.).
        bondtype43: Список ID видов облигаций из bond_type43_mapping
            (1=Амортизируемые облигации, 6=Фикс с известным купоном, и т.д.).
        rating_min: Минимальный рейтинг для фильтрации (из шкалы рейтингов).
        rating_max: Максимальный рейтинг для фильтрации (из шкалы рейтингов).
        emitent_title: Название эмитента для фильтрации облигаций.
        exclude_spob: Если True, исключает облигации с режимом торгов SPOB.
    
    Returns:
        Объект BondsListResponse с отфильтрованным списком облигаций, содержащий:
        - total: Общее количество облигаций в БД (без фильтров)
        - filtered: Количество облигаций после применения всех фильтров
        - skip: Смещение для пагинации (всегда 0)
        - limit: Лимит записей (равен filtered)
        - bonds: Список объектов BondListItem с данными облигаций
    
    Note:
        Вся фильтрация облигаций (кроме фильтрации по эмитенту) выполняется в методе
        BondsRepository.select() на уровне SQL для повышения производительности. Поиск (search)
        выполняется на клиентской стороне и не поддерживается через этот endpoint.
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
    """Загружает последний набор данных об облигациях из MOEX и обновляет кэш.
    
    Выполняет HTTP запрос к API MOEX для получения актуальных данных об облигациях,
    сохраняет данные в файл bonds.json и обновляет таблицу bonds в базе данных.
    Также очищает кэш метаданных (колонки и описания полей) для обеспечения
    актуальности данных.
    
    Returns:
        Словарь с результатом обновления, содержащий:
        - status: Статус операции ("ok")
        - updated: Словарь с информацией о загруженном наборе данных:
          - securities: Количество записей в секции securities
          - marketdata: Количество записей в секции marketdata
          - marketdata_yields: Количество записей в секции marketdata_yields
        - source: URL источника данных
        - metadata_cache_cleared: Флаг очистки кэша метаданных (True)
    
    Raises:
        HTTPException: Если не удалось загрузить данные из MOEX (статус 502)
            или произошла ошибка при обновлении базы данных.
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
    """Получает детальную информацию об облигации по SECID.
    
    Загружает полные данные об облигации из кэша DataLoader, включая данные из
    секций securities, marketdata и marketdata_yields.
    
    Args:
        secid: Идентификатор облигации (SECID) для получения детальной информации.
    
    Returns:
        Объект BondDetail с полными данными об облигации, включающий:
        - securities: Данные из секции securities
        - marketdata: Данные из секции marketdata
        - marketdata_yields: Список данных из секции marketdata_yields
    
    Raises:
        HTTPException: Если облигация с указанным SECID не найдена (статус 404).
    """
    loader = get_data_loader()
    details = await loader.get_bond_details()
    
    if secid not in details:
        raise HTTPException(status_code=404, detail=f"Bond {secid} not found")
    
    bond_data = details[secid]
    return BondDetail(**bond_data)


@router.post("/refresh-coupons")
async def refresh_coupons_data(force_refresh: bool = Query(False, description="Force refresh all coupons, ignoring cache (last_updated date)")):
    """Обновляет данные о купонах для всех облигаций из файла bonds.json.
    
    Читает список SECID из файла bonds.json и обновляет данные о купонах для каждой
    облигации путем загрузки из API MOEX. После успешного обновления синхронизирует
    данные с таблицей coupons в базе данных.
    
    Args:
        force_refresh: Если True, принудительно обновляет все купоны независимо от кэша
            (игнорирует дату last_updated). Если False, обновляет только устаревшие купоны
            (старше 14 дней).
    
    Returns:
        Словарь со статистикой обновления, содержащий:
        - status: Статус операции ("ok")
        - total_bonds: Общее количество облигаций для обработки
        - updated: Количество успешно обновленных облигаций
        - errors: Количество ошибок при обновлении
        - skipped: Количество пропущенных облигаций (отсутствует SECID)
    
    Raises:
        HTTPException: Если произошла критическая ошибка при обновлении данных
            (статус 500).
    
    Note:
        Ошибки при обновлении отдельных облигаций не прерывают процесс. Все ошибки
        логируются, и обработка продолжается для остальных облигаций.
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
    """Получает данные о купонах для одной или нескольких облигаций по SECID.
    
    Поддерживает два режима работы:
    1. Одна облигация: Используется path параметр `{secid}`
       (например, /api/bonds/RU000A0ZZYQ2/coupons)
    2. Несколько облигаций: Используется query параметр `secids`
       (например, /api/bonds/any/coupons?secids=RU000A0ZZYQ2&secids=RU000A0ZZYQ3)
    
    Args:
        secid: Идентификатор облигации (SECID) из path параметра.
            Используется если не указан query параметр secids.
        secids: Опциональный список SECID для пакетного запроса.
            Если указан, имеет приоритет над path параметром secid.
        force_refresh: Если True, принудительно загружает данные из API MOEX,
            игнорируя кэш. По умолчанию False.
    
    Returns:
        Объект CouponsListResponse со списком купонов, содержащий:
        - coupons: Список объектов Coupon с данными купонов (coupondate, value, valueprc)
        - coupon_type: Тип купона ("FIX" или "FLOAT") или None
    
    Raises:
        HTTPException: Если указаны некорректные secids (статус 400),
            если данные не найдены (статус 404), или если произошла ошибка
            при загрузке данных (статус 502 или 500).
    
    Note:
        Если данные отсутствуют или старше 14 дней, автоматически выполняется
        загрузка из API MOEX (если force_refresh=False). При использовании
        query параметра secids возвращаются данные для первой облигации из списка
        (для обратной совместимости).
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
    """Получает данные о купонах для нескольких облигаций по списку SECID.
    
    Выполняет пакетную загрузку данных о купонах для списка облигаций.
    Возвращает купоны, сгруппированные по secid.
    
    Args:
        secids: Список идентификаторов облигаций (SECID) для получения купонов.
            Должен содержать хотя бы один элемент. Дубликаты автоматически удаляются.
    
    Returns:
        Объект MultipleCouponsResponse со списком данных по облигациям, где каждый
        элемент содержит:
        - secid: Идентификатор облигации
        - coupons: Список объектов Coupon с данными купонов
        - coupon_type: Тип купона ("FIX" или "FLOAT") или None, если недоступен
    
    Raises:
        HTTPException: Если все secids некорректны (статус 400) или если произошла
            ошибка при загрузке данных (статус 500).
    
    Note:
        Для облигаций, данные о купонах которых не найдены, возвращается пустой
        список купонов с coupon_type=None.
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
