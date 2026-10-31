"""Центральный сервисный модуль для работы с облигациями.

Реализует ключевую бизнес-логику скринера: фильтрацию, агрегацию данных из различных
источников, расчет производных финансовых показателей и оркестрацию процессов
обновления данных.
"""

from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import httpx

import orjson

from config.settings import settings
from config.paths import DATA_DIR

from app.models import (
    BondDetailDTO,
    BondFilters,
    BondScreenerDTO,
    BondsListResponse,
    round_float_for_api,
)
from app.models.schemasDTO.bond_repository_dto import BondRepositoryRowDTO
from app.repository.db.bonds_repository import BondsRepository
from app.services.emitent_service import get_emitent_service
from app.utils.rating_utils import standardize_rating


def _load_mappings(data_dir: Path) -> Tuple[Dict[int, str], Dict[int, str]]:
    """Загружает маппинги типов и видов облигаций из JSON-файлов.
    
    Считывает файлы bonds_type_mapping.json и bonds_type43_mapping.json для преобразования
    числовых идентификаторов MOEX в понятные текстовые описания.

    Args:
        data_dir (Path): Путь к директории, содержащей файлы маппингов.
    
    Returns:
        Tuple[Dict[int, str], Dict[int, str]]: Кортеж из двух словарей:
            - type_rev: Обратный маппинг типов (ID -> Название).
            - kind_rev: Обратный маппинг видов (ID -> Название).
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
    """Безопасно преобразует строку в объект даты.
    
    Args:
        s (Optional[str]): Строка с датой (обычно в формате YYYY-MM-DD).

    Returns:
        Optional[date]: Объект даты или None, если входная строка пуста, 
            некорректна или содержит заглушку '0000-00-00'.
    """
    if not s or not isinstance(s, str) or s.strip() in ("", "0000-00-00"):
        return None
    try:
        return date.fromisoformat(s.strip()[:10])
    except ValueError:
        return None


def _bond_to_screener_dto(
        bond: BondRepositoryRowDTO,
        #type_rev: Dict[int, str],
        #kind_rev: Dict[int, str],
) -> BondScreenerDTO:
    """Преобразует строку repository в формат BondScreenerDTO для внешнего API.

    Выполняет расчет производных полей (длительность в днях, период купона),
    форматирует даты и подставляет текстовые значения типов/видов облигаций.

    Args:
        bond: Валидированная строка списка облигаций.
        type_rev (Dict[int, str]): Словарь для расшифровки типа облигации.
        kind_rev (Dict[int, str]): Словарь для расшифровки вида облигации.

    Returns:
        BondScreenerDTO: Объект данных, готовый для сериализации в JSON.
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

    rating = standardize_rating(bond.rating)
    ratings: Optional[List[Dict[str, Any]]] = None
    if rating:
        ratings = [
            {"rating_level_name_short_ru": rating, "agency_name_short_ru": getattr(bond, "rating_agency", None) or ""}]

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
        BONDTYPE=bond.bond_type,
        BONDTYPE43=bond.bond_kind,
        COUPON_YIELD_TO_PRICE=round_float_for_api(bond.coupon_yield_to_price),
        COUPON_FREQUENCY=int(bond.coupon_frequency) if bond.coupon_frequency is not None else None,
        DURATION_YEARS=round_float_for_api(bond.duration_years),
    )


async def get_bonds_list(
        filters: BondFilters,
        emitent_title: Optional[str] = None,
        exclude_spob: bool = False
) -> BondsListResponse:

    base_url = settings.DB_REPOSITORY_URL.rstrip("/")
    url = f"{base_url}/api/bonds"
    url_bond_count = f"{base_url}/api/bond_counts"

    # HTTPX's json= encoder expects JSON values; Pydantic's default Python
    # mode leaves maturity dates as datetime.date objects.
    json_filters = filters.model_dump(mode="json")

    emitent_title = emitent_title

    async with httpx.AsyncClient() as client:
        response_bonds = await client.post(
            url=url,
            json=json_filters,
            headers={"Content-Type": "application/json"}
        )
        response_bonds.raise_for_status()
        response_count = await client.get(
            url=url_bond_count,
            params={"exclude_spob": exclude_spob},
        )
        response_count.raise_for_status()

    bonds_data = response_bonds.json()

    bond_rows = [
        BondRepositoryRowDTO.model_validate(item)
        for item in bonds_data
    ]

    print(len(bond_rows))

    total = response_count.json().get("total", 0)

    today = date.today()
    bonds: List[BondScreenerDTO] = []
    for bond in bond_rows:
        try:
            next_coupon = min(
                (
                    coupon
                    for coupon in bond.coupons
                    if coupon.coupondate is not None and coupon.coupondate >= today
                ),
                key=lambda x: x.coupondate,
                default=None
            )

            dto = _bond_to_screener_dto(bond)

            if next_coupon:
                dto.COUPONVALUE = next_coupon.value

            bonds.append(dto)
        except Exception as e:
            continue


    #Фильтр по эмитенту
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


def get_emitent_inn_by_secid(secid: str) -> Optional[str]:
    """Возвращает ИНН эмитента, привязанного к указанной облигации.

    Args:
        secid (str): Идентификатор ценной бумаги (SECID).
    Returns:
        Optional[str]: Строка с ИНН или None, если данные не найдены.
    """
    emitent_service = get_emitent_service()
    emitent_data = emitent_service.get_emitent_by_secid(secid)
    if emitent_data is None:
        return None
    inn = emitent_data.get("emitent_inn")
    return str(inn).strip() if inn else None


def get_reg_number_by_secid(secid: str) -> Optional[str]:
    """Получает государственный регистрационный номер выпуска облигации.

    Args:
        secid (str): Идентификатор ценной бумаги (SECID).
    Returns:
        Optional[str]: Регистрационный номер или None.
    """
    repo = BondsRepository()
    return repo.get_reg_number_by_secid(secid)


def _build_securities_dict(
        bond: Any,
        security: Optional[Any],
        type_rev: Dict[int, str],
        kind_rev: Dict[int, str],
) -> Dict[str, Any]:
    """Формирует словарь данных ценной бумаги в формате ответа MOEX API.

    Используется для предоставления детальной информации об облигации фронтенду
    в привычном для биржевых API виде (ключи в верхнем регистре).

    Args:
        bond (Bond): Объект облигации.
        security (Optional[BondSecurity]): Дополнительные параметры безопасности.
        type_rev (Dict[int, str]): Словарь типов.
        kind_rev (Dict[int, str]): Словарь видов.

    Returns:
        Dict[str, Any]: Словарь с данными в формате 'securities'.
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
        "RATING_LEVEL": standardize_rating(bond.rating),
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
    # Используем нормализованный рейтинг из столбца rating вместо ratings
    if bond.rating:
        sec["RATINGS"] = [{
            "rating_level_name_short_ru": standardize_rating(bond.rating) or "",
            "agency_name_short_ru": bond.rating_agency or "",
        }]
    else:
        sec["RATINGS"] = None
    return sec


def _build_marketdata_dict(
        bond: Any, market_data: Optional[Any]
) -> Dict[str, Any]:
    """Формирует словарь рыночных данных в формате ответа MOEX API.

    Args:
        bond (Bond): Объект облигации.
        market_data (Optional[BondMarketData]): Текущие рыночные показатели.

    Returns:
        Dict[str, Any]: Словарь с данными в формате 'marketdata'.
    """
    if market_data is None:
        return {
            "SECID": bond.secid,
            "BOARDID": bond.boardid,
            "TRADINGSTATUS": bond.trading_status,
        }
    return {
        "SECID": bond.secid,
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
        market_data_yield: Any,
        secid: str,
) -> List[Dict[str, Any]]:
    """Формирует список данных о доходности в формате ответа MOEX API.

    Args:
        market_data_yield: Параметры доходности из repository.
        secid (str): Идентификатор бумаги.

    Returns:
        List[Dict[str, Any]]: Список словарей в формате 'marketdata_yields'.
    """
    entry: Dict[str, Any] = {
        "SECID": secid,
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
        secid: str,
        data_dir: Optional[Path] = None
) -> Optional[BondDetailDTO]:
    """Возвращает максимально полную информацию об облигации.

    Собирает данные из нескольких таблиц (основные данные, параметры листинга,
    текущие котировки и доходность) в единый объект для отображения на странице детализации.

    Args:
        secid (str): Идентификатор ценной бумаги (SECID).
        data_dir (Optional[Path]): Путь к директории маппингов.

    Returns:
        Optional[BondDetailDTO]: Детальная информация об облигации или None.
    """

    type_rev, kind_rev = _load_mappings(data_dir or DATA_DIR)

    repo = BondsRepository()

    result = repo.get_bond_detail_by_secid(secid)

    if result is None:
        return None

    bond, security, market_data, market_data_yield = result

    securities = _build_securities_dict(bond, security, type_rev, kind_rev)

    marketdata = _build_marketdata_dict(bond, market_data)

    marketdata_yields = (
        _build_marketdata_yields_list_from_db(market_data_yield, bond.secid)
        if market_data_yield is not None
        else []
    )

    emitent_inn: Optional[str] = get_emitent_inn_by_secid(secid)

    return BondDetailDTO(
        securities=securities,
        marketdata=marketdata,
        marketdata_yields=marketdata_yields,
        emitent_inn=emitent_inn,
    )
