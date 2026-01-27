# noqa: D100
"""
Сервисный слой выгрузки облигаций (чистая архитектура).

Получает параметры от роутера, вызывает DBBonds.select() для выборки данных
с применением всех фильтров на уровне БД, преобразует строки в BondListItem,
применяет фильтр по эмитенту (если указан), и возвращает готовый ответ для API.

Вся фильтрация облигаций (кроме фильтрации по эмитенту) выполняется в методе
DBBonds.select() на уровне SQL для повышения производительности.
"""

from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import orjson

from app.models.bond import BondListItem
from app.models.filters import BondFilters
from app.models.responses import BondsListResponse
from app.services.db_refresher import DBBonds, DBCoupon
from app.services.emitent_service import get_emitent_service


def _load_mappings(data_dir: Path) -> Tuple[Dict[int, str], Dict[int, str]]:
    """Загружает маппинги bond_type/bond_kind и строит обратные словари id -> str."""
    type_rev: Dict[int, str] = {}
    kind_rev: Dict[int, str] = {}

    type_path = data_dir / "bonds_type_mapping.json"
    if type_path.exists():
        try:
            data = orjson.loads(type_path.read_bytes())
            if isinstance(data, dict):
                for k, v in data.items():
                    if isinstance(v, int):
                        type_rev[v] = str(k)
        except Exception:
            pass

    kind_path = data_dir / "bonds_type43_mapping.json"
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
    if not s or not isinstance(s, str) or s.strip() in ("", "0000-00-00"):
        return None
    try:
        return date.fromisoformat(s.strip()[:10])
    except ValueError:
        return None


def _find_closest_coupon(coupons: List[Dict[str, Any]], current_date: date) -> Optional[Dict[str, Any]]:
    """
    Находит будущий купон с наиболее близкой датой к текущей дате.
    
    Поскольку фильтрация на уровне БД уже возвращает только будущие купоны
    (coupondate >= current_date), выбирается купон с минимальной датой.
    
    Args:
        coupons: Список словарей с данными купонов (уже отфильтрованных по дате)
        current_date: Текущая дата для сравнения (используется для документации)
    
    Returns:
        Словарь с данными ближайшего будущего купона или None, если список пуст
    """
    if not coupons:
        return None
    
    closest_coupon = None
    min_date = None
    
    for coupon in coupons:
        coupondate_str = coupon.get("coupondate")
        if not coupondate_str:
            continue
        
        try:
            coupondate = date.fromisoformat(coupondate_str)
            # Выбираем купон с минимальной датой (ближайший будущий)
            if min_date is None or coupondate < min_date:
                min_date = coupondate
                closest_coupon = coupon
        except (ValueError, TypeError):
            # Пропускаем купоны с некорректной датой
            continue
    
    return closest_coupon


def _get_coupons_for_bonds(
    db: DBCoupon,
    secids: List[str],
    current_date: date
) -> Dict[str, Optional[float]]:
    """
    Получает значения купонов из таблицы coupons для списка облигаций.
    
    Для каждой облигации выбирается купон с наиболее близкой датой к текущей дате,
    и извлекается значение из поля value.
    
    Args:
        db: Экземпляр DBBonds для работы с БД
        secids: Список идентификаторов облигаций
        current_date: Текущая дата для фильтрации и выбора ближайшего купона
    
    Returns:
        Словарь, где ключ - secid, значение - значение купона из поля value или None
    """
    if not secids:
        return {}
    
    # Получаем текущую дату в формате YYYY-MM-DD
    from_date_str = current_date.isoformat()
    
    try:
        # Запрашиваем купоны для всех облигаций с параметром from=текущая дата
        coupons_raw = db.fetch_coupons_raw(
            secids=secids,
            from_date=from_date_str
        )
    except Exception:
        # В случае ошибки возвращаем пустой словарь
        return {}
    
    # Группируем купоны по secid
    coupons_by_secid: Dict[str, List[Dict[str, Any]]] = {}
    for coupon in coupons_raw:
        secid = coupon.get("secid")
        if secid:
            if secid not in coupons_by_secid:
                coupons_by_secid[secid] = []
            coupons_by_secid[secid].append(coupon)
    
    # Для каждой облигации находим ближайший купон и извлекаем value
    result: Dict[str, Optional[float]] = {}
    for secid in secids:
        coupons = coupons_by_secid.get(secid, [])
        closest_coupon = _find_closest_coupon(coupons, current_date)
        
        if closest_coupon:
            value = closest_coupon.get("value")
            # Преобразуем value в float, если возможно
            if value is not None:
                try:
                    result[secid] = float(value)
                except (ValueError, TypeError):
                    result[secid] = None
            else:
                result[secid] = None
        else:
            # Купон не найден - ставим None (прочерк)
            result[secid] = None
    
    return result


def _row_to_bond_list_item(
    row: Dict[str, Any],
    type_rev: Dict[int, str],
    kind_rev: Dict[int, str],
) -> BondListItem:
    """Преобразует сырую строку БД в BondListItem с учётом вычисляемых полей."""
    maturity_date = _parse_date(row.get("maturity_date"))
    coupon_freq = row.get("coupon_frequency")
    coupon_period: Optional[int] = None
    if coupon_freq is not None and isinstance(coupon_freq, (int, float)) and float(coupon_freq) > 0:
        try:
            coupon_period = int(round(365 / float(coupon_freq)))
        except (ValueError, ZeroDivisionError):
            pass

    duration_years = row.get("duration_years")
    duration_days: Optional[float] = None
    if duration_years is not None and isinstance(duration_years, (int, float)):
        try:
            duration_days = float(duration_years) * 365
        except (ValueError, TypeError):
            pass

    rating = (row.get("rating") or "").strip() or None
    ratings: Optional[List[Dict[str, Any]]] = None
    if rating:
        ratings = [
            {"rating_level_name_short_ru": rating, "agency_name_short_ru": ""},
        ]

    bond_type_id = row.get("bond_type")
    bond_kind_id = row.get("bond_kind")
    bondtype = type_rev.get(bond_type_id) if isinstance(bond_type_id, int) else None
    bondtype43 = kind_rev.get(bond_kind_id) if isinstance(bond_kind_id, int) else None

    return BondListItem(
        SECID=str(row.get("secid") or ""),
        BOARDID=str(row.get("boardid") or ""),
        SHORTNAME=str(row.get("name") or ""),
        SECNAME=str(row.get("name") or "") or None,
        ISIN=str(row.get("isin") or "").strip() or None,
        COUPONPERCENT=float(row["coupon_percent"]) if row.get("coupon_percent") is not None else None,
        MATDATE=maturity_date,
        STATUS=None,
        TRADINGSTATUS=None,
        FACEVALUE=float(row["face_value"]) if row.get("face_value") is not None else None,
        PREVPRICE=float(row["current_price"]) if row.get("current_price") is not None else None,
        YIELDATPREVWAPRICE=float(row["yield_to_maturity"]) if row.get("yield_to_maturity") is not None else None,
        NEXTCOUPON=None,
        BOARDNAME=None,
        CALLOPTIONDATE=None,
        PUTOPTIONDATE=None,
        ACCRUEDINT=float(row["accrued_interest"]) if row.get("accrued_interest") is not None else None,
        COUPONPERIOD=coupon_period,
        COUPONVALUE=float(row["coupon_value"]) if row.get("coupon_value") is not None else None,
        DURATION=duration_days,
        DURATIONWAPRICE=None,
        CURRENCYID=str(row.get("currency") or "").strip() or None,
        FACEUNIT=str(row.get("currency") or "").strip() or None,
        LISTLEVEL=int(row["listing_level"]) if row.get("listing_level") is not None else None,
        RATING_AGENCY=None,
        RATING_LEVEL=rating,
        RATINGS=ratings,
        BONDTYPE=bondtype,
        BONDTYPE43=bondtype43,
        COUPON_TYPE=None,
        COUPON_YIELD_TO_PRICE=float(row["coupon_yield_to_price"]) if row.get("coupon_yield_to_price") is not None else None,
        COUPON_FREQUENCY=int(row["coupon_frequency"]) if row.get("coupon_frequency") is not None else None,
        DURATION_YEARS=float(row["duration_years"]) if row.get("duration_years") is not None else None,
    )


def get_bonds_list(
    filters: BondFilters,
    emitent_title: Optional[str] = None,
    exclude_spob: bool = False,
    db_path: Optional[Path] = None,
    data_dir: Optional[Path] = None,
) -> BondsListResponse:
    """
    Выгрузка списка облигаций с фильтрами.

    Вызывает DBBonds.select() для получения данных с применением всех фильтров на уровне БД.
    Преобразует сырые данные из БД в BondListItem, применяет фильтр по эмитенту
    (если указан), и возвращает BondsListResponse.
    
    Вся фильтрация облигаций (кроме фильтрации по эмитенту) выполняется в методе
    DBBonds.select() на уровне SQL для повышения производительности.
    """
    if data_dir is None:
        backend = Path(__file__).resolve().parent.parent.parent
        data_dir = backend / "app" / "data"
    data_dir = Path(data_dir)

    type_rev, kind_rev = _load_mappings(data_dir)

    db = DBBonds(db_path=db_path, data_dir=data_dir)

    # Используем универсальный метод select, который применяет все фильтры на уровне БД
    # Фронтенд теперь отправляет ID напрямую, преобразование не требуется
    # bondtype и bondtype43 уже содержат ID (числа), которые передаются напрямую в SQL-запрос
    raw = db.select(
        filters=filters,
        bond_type_ids=filters.bondtype,
        bond_kind_ids=filters.bondtype43,
        exclude_spob=exclude_spob,
    )

    # total — число всех облигаций в БД (без фильтров), для совместимости с API
    total = db.count_bonds(exclude_spob=False)

    # Преобразуем в BondListItem
    bonds: List[BondListItem] = []
    for r in raw:
        try:
            bonds.append(_row_to_bond_list_item(r, type_rev, kind_rev))
        except Exception:
            continue

    # Получаем купоны из таблицы coupons для всех облигаций
    # Используем текущую дату для фильтрации и выбора ближайшего купона

    current_date = date.today()
    secids = [b.SECID for b in bonds if b.SECID]
    dbcoupon = DBCoupon()
    coupons_map = _get_coupons_for_bonds(dbcoupon, secids, current_date)
    
    # Обновляем COUPONVALUE для каждой облигации из данных купонов
    for bond in bonds:
        if bond.SECID in coupons_map:
            bond.COUPONVALUE = coupons_map[bond.SECID]

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
