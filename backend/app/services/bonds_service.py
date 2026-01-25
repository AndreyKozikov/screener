# noqa: D100
"""
Сервисный слой выгрузки облигаций (чистая архитектура).

Получает параметры от роутера, вызывает DBBonds для выборки сырых данных,
применяет фильтры по рейтингу и эмитенту, преобразует строки в BondListItem,
вычисляет производные поля (COUPON_YIELD_TO_PRICE, COUPON_FREQUENCY, DURATION_YEARS)
и возвращает готовый ответ для API.
"""

from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import orjson

from app.models.bond import BondListItem
from app.models.filters import BondFilters
from app.models.responses import BondsListResponse
from app.services.db_refresher import DBBonds
from app.services.emitent_service import get_emitent_service
from app.services.bond_filter import is_rating_in_range


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

    Вызывает DBBonds (только SQL), применяет фильтры по рейтингу и эмитенту
    в сервисном слое, преобразует данные в формат для фронта и возвращает
    BondsListResponse.
    """
    if data_dir is None:
        backend = Path(__file__).resolve().parent.parent.parent
        data_dir = backend / "app" / "data"
    data_dir = Path(data_dir)

    type_rev, kind_rev = _load_mappings(data_dir)

    # Маппинг bondtype/bondtype43 (строка) -> id для SQL
    type_fwd: Dict[str, int] = {}
    kind_fwd: Dict[str, int] = {}
    type_path = data_dir / "bonds_type_mapping.json"
    kind_path = data_dir / "bonds_type43_mapping.json"
    if type_path.exists():
        try:
            type_fwd = orjson.loads(type_path.read_bytes())
        except Exception:
            pass
    if kind_path.exists():
        try:
            kind_fwd = orjson.loads(kind_path.read_bytes())
        except Exception:
            pass

    bond_type_ids: Optional[List[int]] = None
    if filters.bondtype:
        bond_type_ids = [type_fwd[t] for t in filters.bondtype if t in type_fwd]
        if not bond_type_ids:
            bond_type_ids = None

    bond_kind_ids: Optional[List[int]] = None
    if filters.bondtype43:
        bond_kind_ids = [kind_fwd[k] for k in filters.bondtype43 if k in kind_fwd]
        if not bond_kind_ids:
            bond_kind_ids = None

    mat_from = filters.matdate_from.isoformat() if filters.matdate_from else None
    mat_to = filters.matdate_to.isoformat() if filters.matdate_to else None

    db = DBBonds(db_path=db_path, data_dir=data_dir)

    raw = db.fetch_bonds_raw(
        coupon_percent_min=filters.coupon_min,
        coupon_percent_max=filters.coupon_max,
        yield_to_maturity_min=filters.yield_min,
        yield_to_maturity_max=filters.yield_max,
        coupon_yield_to_price_min=filters.coupon_yield_min,
        coupon_yield_to_price_max=filters.coupon_yield_max,
        maturity_date_from=mat_from,
        maturity_date_to=mat_to,
        listlevel=filters.listlevel,
        currency=filters.faceunit,
        bond_type_ids=bond_type_ids,
        bond_kind_ids=bond_kind_ids,
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

    # Фильтр по рейтингу (в сервисном слое)
    if filters.rating_min is not None or filters.rating_max is not None:
        bonds = [b for b in bonds if is_rating_in_range(b.RATING_LEVEL, filters.rating_min, filters.rating_max)]

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
