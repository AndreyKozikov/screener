"""Сервисный слой для работы с облигациями.

Этот модуль реализует бизнес-логику для получения и фильтрации списка облигаций.
Получает параметры от роутера, вызывает BondsRepository.select() для выборки данных
с применением всех фильтров на уровне БД, трансформирует Bond в BondScreenerDTO,
применяет фильтр по эмитенту (если указан), и возвращает готовый ответ для API.

Основные функции:
    get_bonds_list(): Получение списка облигаций с применением фильтров.

Note:
    Вся фильтрация облигаций (кроме фильтрации по эмитенту) выполняется в методе
    BondsRepository.select() на уровне SQL для повышения производительности.
"""

from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import orjson

from config.settings import settings

from app.models.bond import Bond, BondMarketData, BondMarketDataYield, BondSecurity
from app.models.bonds_dto import BondDetailDTO, BondScreenerDTO, round_float_for_api
from app.models.filters import BondFilters
from app.models.responses import BondsListResponse
from app.repository.db.bonds_repository import BondsRepository
from app.repository.db_orchestrator import DBOrchestrator
from app.services.coupon_service import get_coupon_service
from app.services.data_loader import get_data_loader
from app.services.emitent_service import get_emitent_service
from app.utils.logger import get_data_update_logger


def _load_mappings(data_dir: Path) -> Tuple[Dict[int, str], Dict[int, str]]:
    """Загружает маппинги типов и видов облигаций и строит обратные словари.
    
    Загружает маппинги из JSON файлов bonds_type_mapping.json и bonds_type43_mapping.json
    и создает обратные словари для преобразования числовых ID в строковые значения.
    
    Args:
        data_dir: Путь к директории с JSON файлами маппингов.
    
    Returns:
        Кортеж из двух словарей:
        - type_rev: Обратный маппинг типов облигаций (ID -> строка).
        - kind_rev: Обратный маппинг видов облигаций (ID -> строка).
    """
    type_rev: Dict[int, str] = {}
    kind_rev: Dict[int, str] = {}

    from config.paths import BONDS_TYPE_MAPPING_JSON, BONDS_TYPE43_MAPPING_JSON
    type_path = data_dir / BONDS_TYPE_MAPPING_JSON
    if type_path.exists():
        try:
            data = orjson.loads(type_path.read_bytes())
            if isinstance(data, dict):
                for k, v in data.items():
                    if isinstance(v, int):
                        type_rev[v] = str(k)
        except Exception:
            pass

    kind_path = data_dir / BONDS_TYPE43_MAPPING_JSON
    if kind_path.exists():
        try:
            data = orjson.loads(kind_path.read_bytes())
            if isinstance(data, dict):
                for k, v in data.items():
                    if isinstance(v, int):
                        kind_rev[v] = str(k)
        except Exception:
            pass

    return type_rev, kind_rev


def _parse_date(s: Optional[str]) -> Optional[date]:
    """Парсит строку даты в объект date.
    
    Преобразует строку с датой в формате ISO (YYYY-MM-DD) в объект date.
    Обрабатывает некорректные значения и пустые строки.
    
    Args:
        s: Строка с датой в формате ISO (YYYY-MM-DD) или None.
            Если строка содержит "0000-00-00" или пустая, возвращает None.
    
    Returns:
        Объект date или None, если строка некорректна, пуста или равна "0000-00-00".
    """
    if not s or not isinstance(s, str) or s.strip() in ("", "0000-00-00"):
        return None
    try:
        return date.fromisoformat(s.strip()[:10])
    except ValueError:
        return None


def _bond_to_screener_dto(
    bond: Bond,
    type_rev: Dict[int, str],
    kind_rev: Dict[int, str],
) -> BondScreenerDTO:
    """Трансформирует Bond (модель БД) в BondScreenerDTO для API.

    Использует маппинги type_rev и kind_rev для преобразования числовых ID
    типов/видов облигаций в строковые названия. Все расчётные float-поля
    округляются до 2 знаков после запятой.

    Args:
        bond: Объект Bond из bonds_repository.select().
        type_rev: Обратный маппинг типов облигаций (ID -> строка).
        kind_rev: Обратный маппинг видов облигаций (ID -> строка).

    Returns:
        Объект BondScreenerDTO для ответа API.
    """
    maturity_date = _parse_date(bond.maturity_date)
    coupon_period: Optional[int] = None
    if bond.coupon_frequency is not None and bond.coupon_frequency > 0:
        try:
            coupon_period = int(round(365 / float(bond.coupon_frequency)))
        except (ValueError, ZeroDivisionError):
            pass

    duration_days: Optional[float] = None
    if bond.duration_years is not None:
        try:
            duration_days = float(bond.duration_years) * 365
        except (ValueError, TypeError):
            pass

    duration_days_from_bond = getattr(bond, "duration", None)
    if duration_days_from_bond is not None:
        duration_days = duration_days_from_bond

    rating = (bond.rating or "").strip() or None
    ratings: Optional[List[Dict[str, Any]]] = None
    if rating:
        ratings = [{"rating_level_name_short_ru": rating, "agency_name_short_ru": ""}]
    if getattr(bond, "ratings", None) and isinstance(bond.ratings, str):
        try:
            ratings = orjson.loads(bond.ratings)
        except (orjson.JSONDecodeError, TypeError):
            pass

    bond_type_str = type_rev.get(bond.bond_type) if isinstance(bond.bond_type, int) else None
    bond_kind_str = kind_rev.get(bond.bond_kind) if isinstance(bond.bond_kind, int) else None

    next_coupon_date = _parse_date(bond.next_coupon) if getattr(bond, "next_coupon", None) else None
    call_option_date = _parse_date(bond.call_option_date) if getattr(bond, "call_option_date", None) else None
    put_option_date = _parse_date(bond.put_option_date) if getattr(bond, "put_option_date", None) else None

    coupon_period_val = bond.coupon_period if getattr(bond, "coupon_period", None) is not None else coupon_period
    duration_waprice_from_bond = getattr(bond, "duration_waprice", None)

    return BondScreenerDTO(
        SECID=str(bond.secid or ""),
        BOARDID=str(bond.boardid or ""),
        SHORTNAME=str(bond.name or ""),
        SECNAME=(bond.secname or bond.name or "") or None,
        ISIN=(bond.isin or "").strip() or None,
        COUPONPERCENT=round_float_for_api(bond.coupon_percent),
        MATDATE=maturity_date,
        STATUS=getattr(bond, "status", None),
        TRADINGSTATUS=getattr(bond, "trading_status", None),
        FACEVALUE=round_float_for_api(bond.face_value),
        PREVPRICE=round_float_for_api(bond.current_price),
        YIELDATPREVWAPRICE=round_float_for_api(bond.yield_to_maturity),
        NEXTCOUPON=next_coupon_date,
        BOARDNAME=getattr(bond, "board_name", None),
        CALLOPTIONDATE=call_option_date,
        PUTOPTIONDATE=put_option_date,
        ACCRUEDINT=round_float_for_api(bond.accrued_interest),
        COUPONPERIOD=coupon_period_val,
        COUPONVALUE=round_float_for_api(bond.coupon_value),
        DURATION=round_float_for_api(duration_days),
        DURATIONWAPRICE=duration_waprice_from_bond,
        CURRENCYID=(bond.currency or "").strip() or None,
        FACEUNIT=(getattr(bond, "face_unit", None) or "").strip() or None,
        LISTLEVEL=bond.listing_level,
        RATING_AGENCY=getattr(bond, "rating_agency", None),
        RATING_LEVEL=rating,
        RATINGS=ratings,
        BONDTYPE=bond_type_str,
        BONDTYPE43=bond_kind_str,
        COUPON_YIELD_TO_PRICE=round_float_for_api(bond.coupon_yield_to_price),
        COUPON_FREQUENCY=int(bond.coupon_frequency) if bond.coupon_frequency is not None else None,
        DURATION_YEARS=round_float_for_api(bond.duration_years),
    )


def get_bonds_list(
    filters: BondFilters,
    emitent_title: Optional[str] = None,
    exclude_spob: bool = False,
    db_path: Optional[Path] = None,
    data_dir: Optional[Path] = None,
) -> BondsListResponse:
    """Получает список облигаций с применением фильтров.

    Основная функция сервисного слоя для получения списка облигаций. Вызывает
    BondsRepository.select() для получения данных с применением всех фильтров на уровне БД,
    трансформирует Bond в BondScreenerDTO (с округлением float до 2 знаков и маппингом
    типов/видов в строки), загружает данные о купонах, применяет фильтр по эмитенту
    (если указан), и возвращает BondsListResponse.

    Args:
        filters: Объект BondFilters с параметрами фильтрации облигаций.
            Включает фильтры по проценту купона, доходности, дате погашения,
            уровню листинга, валюте, типу облигации, виду облигации и рейтингу.
        emitent_title: Опциональное название эмитента для фильтрации облигаций.
            Если указано, возвращаются только облигации указанного эмитента.
        exclude_spob: Если True, исключает облигации с режимом торгов SPOB.
        db_path: Опциональный путь к файлу базы данных. Если не указан,
            используется путь по умолчанию.
        data_dir: Опциональный путь к директории с JSON файлами данных.
            Если не указан, используется путь по умолчанию.

    Returns:
        Объект BondsListResponse с отфильтрованным списком облигаций, содержащий:
        - total: Общее количество облигаций в БД (без фильтров).
        - filtered: Количество облигаций после применения всех фильтров.
        - skip: Смещение для пагинации (всегда 0).
        - limit: Лимит записей (равен filtered).
        - bonds: Список объектов BondScreenerDTO с данными облигаций.

    Note:
        Вся фильтрация облигаций (кроме фильтрации по эмитенту) выполняется в методе
        BondsRepository.select() на уровне SQL для повышения производительности. Фильтрация
        по эмитенту выполняется в сервисном слое, так как требует дополнительных данных
        из таблицы эмитентов.
    """
    if data_dir is None:
        from config.paths import DATA_DIR
        data_dir = DATA_DIR
    data_dir = Path(data_dir)

    type_rev, kind_rev = _load_mappings(data_dir)

    db = BondsRepository(db_path=db_path)

    # Выборка через SQLModel API; возвращаются объекты Bond
    try:
        bond_rows = db.select(
            filters=filters,
            bond_type_ids=filters.bondtype,
            bond_kind_ids=filters.bondtype43,
            exclude_spob=exclude_spob,
        )
    except Exception as e:
        if "no such table" in str(e).lower():
            bond_rows = []
        else:
            raise

    try:
        total = db.count_bonds(exclude_spob=False)
    except Exception as e:
        if "no such table" in str(e).lower():
            total = 0
        else:
            raise

    bonds: List[BondScreenerDTO] = []
    for bond in bond_rows:
        try:
            bonds.append(_bond_to_screener_dto(bond, type_rev, kind_rev))
        except Exception:
            continue

    # Получаем значения ближайших купонов через CouponService
    current_date = date.today()
    secids = [b.SECID for b in bonds if b.SECID]
    coupons_map = get_coupon_service().get_nearest_coupon_values(
        secids=secids,
        from_date=current_date,
    )

    # Обновляем COUPONVALUE для каждой облигации из данных купонов (округление до 2 знаков)
    for dto in bonds:
        if dto.SECID in coupons_map:
            dto.COUPONVALUE = round_float_for_api(coupons_map[dto.SECID])

    # Фильтр по эмитенту
    if emitent_title and str(emitent_title).strip():
        emitent_svc = get_emitent_service()
        secid_to_title = emitent_svc.get_secid_to_emitent_title_index()
        title_stripped = str(emitent_title).strip()
        bonds = [b for b in bonds if secid_to_title.get(b.SECID) == title_stripped]

    return BondsListResponse(
        total=total,
        filtered=len(bonds),
        skip=0,
        limit=len(bonds),
        bonds=bonds,
    )


def refresh_bonds_data(
    source_url: Optional[str] = None,
    db_path: Optional[Path] = None,
    data_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """Загружает данные облигаций из MOEX и сохраняет в БД.

    Координирует пайплайн: загрузка через DataLoader.refresh_bonds_dataset(),
    миграция в таблицы bonds, bondsecurity, bondmarketdata, bondmarketdatayield
    через DBOrchestrator, очистка кэша метаданных.

    Args:
        source_url: URL для загрузки JSON. Если None — используется settings.MOEX_BONDS_URL.
        db_path: Путь к БД. Если None — используется путь по умолчанию.
        data_dir: Путь к директории данных. Если None — используется путь по умолчанию.

    Returns:
        Словарь с результатом: status, updated (securities, marketdata, marketdata_yields),
        source, metadata_cache_cleared.

    Raises:
        RuntimeError: Если не удалось загрузить данные из MOEX.
    """
    log = get_data_update_logger()
    url = source_url or settings.MOEX_BONDS_URL
    try:
        log.info("[refresh_bonds_data] Step 1: Loading data from MOEX (%s)", url)
        loader = get_data_loader()
        summary = loader.refresh_bonds_dataset(url)
        log.info("[refresh_bonds_data] Step 1 OK: Loaded %s securities", summary.get("securities", 0))
    except Exception as e:
        log.exception("[refresh_bonds_data] Step 1 FAILED: Load from MOEX: %s", e)
        raise
    try:
        log.info("[refresh_bonds_data] Step 2: Migrating to DB")
        orchestrator = DBOrchestrator(db_path=db_path, data_dir=data_dir)
        ok = orchestrator.migrate("bonds")
        if not ok:
            log.warning("[refresh_bonds_data] Step 2: DB migrate returned False")
        else:
            log.info("[refresh_bonds_data] Step 2 OK: DB migration completed")
    except Exception as e:
        log.exception("[refresh_bonds_data] Step 2 FAILED: DB migration: %s", e)
        raise
    try:
        log.info("[refresh_bonds_data] Step 3: Clearing metadata cache")
        loader.clear_metadata_cache()
        log.info("[refresh_bonds_data] Step 3 OK: Cache cleared")
    except Exception as e:
        log.exception("[refresh_bonds_data] Step 3 FAILED: Cache clear: %s", e)
        raise
    return {
        "status": "ok",
        "updated": summary,
        "source": url,
        "metadata_cache_cleared": True,
    }


def _build_securities_dict(
    bond: Bond,
    security: Optional[BondSecurity],
    type_rev: Dict[int, str],
    kind_rev: Dict[int, str],
) -> Dict[str, Any]:
    """Собирает словарь securities в формате MOEX API (UPPERCASE ключи).

    Args:
        bond: Объект Bond из БД.
        security: BondSecurity или None.
        type_rev: Маппинг bond_type ID -> строка.
        kind_rev: Маппинг bond_kind ID -> строка.

    Returns:
        Словарь с полями секции securities.
    """
    sec: Dict[str, Any] = {
        "SECID": bond.secid,
        "BOARDID": security.boardid if security and security.boardid else bond.boardid,
        "SHORTNAME": bond.name,
        "SECNAME": bond.secname,
        "ISIN": bond.isin,
        "PREVPRICE": bond.current_price,
        "YIELDATPREVWAPRICE": bond.yield_to_maturity,
        "COUPONVALUE": bond.coupon_value,
        "COUPONPERCENT": bond.coupon_percent,
        "NEXTCOUPON": bond.next_coupon,
        "ACCRUEDINT": bond.accrued_interest,
        "FACEVALUE": bond.face_value,
        "BOARDNAME": bond.board_name,
        "STATUS": bond.status,
        "MATDATE": bond.maturity_date,
        "CURRENCYID": bond.currency,
        "COUPONPERIOD": bond.coupon_period,
        "LISTLEVEL": bond.listing_level,
        "OFFERDATE": bond.offer_date,
        "CALLOPTIONDATE": bond.call_option_date,
        "PUTOPTIONDATE": bond.put_option_date,
        "DURATIONWAPRICE": bond.duration_waprice,
        "RATING_LEVEL": bond.rating,
        "RATING_AGENCY": bond.rating_agency,
        "FACEUNIT": bond.face_unit,
    }
    if security:
        sec["PREVWAPRICE"] = security.prev_waprice
        sec["YIELDATPREVWAPRICE"] = sec.get("YIELDATPREVWAPRICE") or security.yield_at_prev_waprice
        sec["PREVPRICE"] = sec.get("PREVPRICE") or security.prev_price
        sec["LOTSIZE"] = security.lot_size
        sec["REGNUMBER"] = security.reg_number
        sec["DECIMALS"] = security.decimals
        sec["ISSUESIZE"] = security.issue_size
        sec["PREVLEGALCLOSEPRICE"] = security.prev_legal_close_price
        sec["PREVDATE"] = security.prev_date.isoformat() if security.prev_date else None
        sec["REMARKS"] = security.remarks
        sec["MARKETCODE"] = security.market_code
        sec["INSTRID"] = security.instr_id
        sec["SECTORID"] = security.sector_id
        sec["MINSTEP"] = security.min_step
        sec["FACEUNIT"] = sec.get("FACEUNIT") or bond.face_unit or security.face_unit
        sec["BUYBACKPRICE"] = security.buyback_price
        sec["BUYBACKDATE"] = security.buyback_date.isoformat() if security.buyback_date else None
        sec["LATNAME"] = security.lat_name
        sec["ISSUESIZEPLACED"] = security.issue_size_placed
        sec["SECTYPE"] = security.sec_type
        sec["SETTLEDATE"] = security.settle_date.isoformat() if security.settle_date else None
        sec["LOTVALUE"] = security.lot_value
        sec["FACEVALUEONSETTLEDATE"] = security.face_value_on_settle_date
        sec["DATEYIELDFROMISSUER"] = (
            security.date_yield_from_issuer.isoformat() if security.date_yield_from_issuer else None
        )
    else:
        sec["FACEUNIT"] = bond.face_unit
        sec["LOTSIZE"] = None
        sec["REGNUMBER"] = None
    bond_type_str = type_rev.get(bond.bond_type) if bond.bond_type is not None else None
    bond_kind_str = kind_rev.get(bond.bond_kind) if bond.bond_kind is not None else None
    sec["BONDTYPE"] = bond_type_str
    sec["BONDTYPE43"] = bond_kind_str
    if bond.ratings:
        try:
            sec["RATINGS"] = orjson.loads(bond.ratings)
        except (orjson.JSONDecodeError, TypeError):
            sec["RATINGS"] = None
    else:
        sec["RATINGS"] = None
    return sec


def _build_marketdata_dict(
    bond: Bond, market_data: Optional[BondMarketData]
) -> Dict[str, Any]:
    """Собирает словарь marketdata в формате MOEX API (UPPERCASE ключи).

    Args:
        bond: Объект Bond (для BOARDID, TRADINGSTATUS).
        market_data: BondMarketData или None.

    Returns:
        Словарь с полями секции marketdata.
    """
    if market_data is None:
        return {
            "SECID": bond.secid,
            "BOARDID": bond.boardid,
            "TRADINGSTATUS": bond.trading_status,
        }
    return {
        "SECID": market_data.secid,
        "BOARDID": market_data.boardid if market_data.boardid else bond.boardid,
        "BID": market_data.bid,
        "OFFER": market_data.offer,
        "SPREAD": market_data.spread,
        "BIDDEPTH": market_data.bid_depth,
        "OFFERDEPTH": market_data.offer_depth,
        "OPEN": market_data.open_price,
        "LOW": market_data.low,
        "HIGH": market_data.high,
        "LAST": market_data.last_price,
        "LASTCHANGE": market_data.last_change,
        "LASTCHANGEPRCNT": market_data.last_change_prcnt,
        "QTY": market_data.qty,
        "VALUE": market_data.value,
        "VALUE_USD": market_data.value_usd,
        "WAPRICE": market_data.waprice,
        "LASTCNGTOLASTWAPRICE": market_data.last_cnt_to_last_waprice,
        "WAPTOPREVWAPRICEPRCNT": market_data.wap_to_prev_waprice_prcnt,
        "WAPTOPREVWAPRICE": market_data.wap_to_prev_waprice,
        "CLOSEPRICE": market_data.close_price,
        "MARKETPRICETODAY": market_data.market_price_today,
        "MARKETPRICE": market_data.market_price,
        "LASTTOPREVPRICE": market_data.last_to_prev_price,
        "NUMTRADES": market_data.num_trades,
        "VOLTODAY": market_data.vol_today,
        "VALTODAY": market_data.val_today,
        "VALTODAY_USD": market_data.val_today_usd,
        "ETFSETTLEPRICE": market_data.etf_settle_price,
        "TRADINGSTATUS": bond.trading_status,
        "UPDATETIME": market_data.update_time,
        "DURATION": bond.duration,
        "YIELD": bond.yield_to_maturity,
    }


def _build_marketdata_yields_list_from_db(
    market_data_yield: BondMarketDataYield,
) -> List[Dict[str, Any]]:
    """Преобразует BondMarketDataYield в список словарей формата MOEX API.

    Данные из таблицы bondmarketdatayield (UPPERCASE ключи для фронтенда).

    Args:
        market_data_yield: Запись из таблицы bondmarketdatayield.

    Returns:
        Список из одного словаря с полями marketdata_yields.
    """
    entry: Dict[str, Any] = {
        "SECID": market_data_yield.secid,
        "BOARDID": market_data_yield.boardid,
        "PRICE": market_data_yield.price,
        "YIELDDATE": market_data_yield.yield_date,
        "ZCYCMOMENT": market_data_yield.zcyc_moment,
        "YIELDDATETYPE": market_data_yield.yield_date_type,
        "EFFECTIVEYIELD": market_data_yield.effective_yield,
        "DURATION": market_data_yield.duration,
        "ZSPREADBP": market_data_yield.zspread_bp,
        "GSPREADBP": market_data_yield.gspread_bp,
        "WAPRICE": market_data_yield.waprice,
        "EFFECTIVEYIELDWAPRICE": market_data_yield.effective_yield_waprice,
        "DURATIONWAPRICE": market_data_yield.duration_waprice,
        "IR": market_data_yield.ir,
        "ICPI": market_data_yield.icpi,
        "BEI": market_data_yield.bei,
        "CBR": market_data_yield.cbr,
        "YIELDTOOFFER": market_data_yield.yield_to_offer,
        "YIELDLASTCOUPON": market_data_yield.yield_last_coupon,
        "TRADEMOMENT": market_data_yield.trade_moment,
        "SEQNUM": market_data_yield.seqnum,
        "SYSTIME": market_data_yield.systime,
    }
    return [entry]


def get_bond_detail(
    secid: str, db_path: Optional[Path] = None, data_dir: Optional[Path] = None
) -> Optional[BondDetailDTO]:
    """Получает детальную информацию об облигации из БД в формате DTO.

    Загружает Bond, BondSecurity и BondMarketData, преобразует в структуру
    BondDetailDTO (securities, marketdata, marketdata_yields) для фронтенда.

    Args:
        secid: Идентификатор ценной бумаги.
        db_path: Путь к БД. Если None — используется путь по умолчанию.
        data_dir: Путь к директории маппингов. Если None — используется путь по умолчанию.

    Returns:
        BondDetailDTO или None, если облигация не найдена.
    """
    if data_dir is None:
        from config.paths import DATA_DIR
        data_dir = DATA_DIR
    data_dir = Path(data_dir)
    type_rev, kind_rev = _load_mappings(data_dir)
    repo = BondsRepository(db_path=db_path)
    result = repo.get_bond_detail_by_secid(secid)
    if result is None:
        return None
    bond, security, market_data, market_data_yield = result
    securities = _build_securities_dict(bond, security, type_rev, kind_rev)
    marketdata = _build_marketdata_dict(bond, market_data)
    marketdata_yields = (
        _build_marketdata_yields_list_from_db(market_data_yield)
        if market_data_yield is not None
        else []
    )
    return BondDetailDTO(
        securities=securities,
        marketdata=marketdata,
        marketdata_yields=marketdata_yields,
    )
