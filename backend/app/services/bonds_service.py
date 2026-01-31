"""Сервисный слой для работы с облигациями.

Этот модуль реализует бизнес-логику для получения и фильтрации списка облигаций.
Получает параметры от роутера, вызывает BondsRepository.select() для выборки данных
с применением всех фильтров на уровне БД, преобразует строки в BondListItem,
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

from app.models.bond import Bond, BondListItem
from app.models.filters import BondFilters
from app.models.responses import BondsListResponse
from app.repository.db.bonds_repository import BondsRepository
from app.services.coupon_service import get_coupon_service
from app.services.emitent_service import get_emitent_service


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


def _bond_to_list_item(
    bond: Bond,
    type_rev: Dict[int, str],
    kind_rev: Dict[int, str],
) -> BondListItem:
    """Преобразует объект Bond из БД в BondListItem для API.

    Вычисляет производные поля (COUPONPERIOD из coupon_frequency, DURATION в днях
    из duration_years) и применяет обратные маппинги типов/видов облигаций.

    Args:
        bond: Объект Bond из bonds_repository.select().
        type_rev: Обратный маппинг типов облигаций (ID -> строка).
        kind_rev: Обратный маппинг видов облигаций (ID -> строка).

    Returns:
        Объект BondListItem для ответа API.
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

    rating = (bond.rating or "").strip() or None
    ratings: Optional[List[Dict[str, Any]]] = None
    if rating:
        ratings = [{"rating_level_name_short_ru": rating, "agency_name_short_ru": ""}]

    bondtype = type_rev.get(bond.bond_type) if isinstance(bond.bond_type, int) else None
    bondtype43 = kind_rev.get(bond.bond_kind) if isinstance(bond.bond_kind, int) else None

    return BondListItem(
        SECID=str(bond.secid or ""),
        BOARDID=str(bond.boardid or ""),
        SHORTNAME=str(bond.name or ""),
        SECNAME=str(bond.name or "") or None,
        ISIN=(bond.isin or "").strip() or None,
        COUPONPERCENT=bond.coupon_percent,
        MATDATE=maturity_date,
        STATUS=None,
        TRADINGSTATUS=None,
        FACEVALUE=bond.face_value,
        PREVPRICE=bond.current_price,
        YIELDATPREVWAPRICE=bond.yield_to_maturity,
        NEXTCOUPON=None,
        BOARDNAME=None,
        CALLOPTIONDATE=None,
        PUTOPTIONDATE=None,
        ACCRUEDINT=bond.accrued_interest,
        COUPONPERIOD=coupon_period,
        COUPONVALUE=bond.coupon_value,
        DURATION=duration_days,
        DURATIONWAPRICE=None,
        CURRENCYID=(bond.currency or "").strip() or None,
        FACEUNIT=(bond.currency or "").strip() or None,
        LISTLEVEL=bond.listing_level,
        RATING_AGENCY=None,
        RATING_LEVEL=rating,
        RATINGS=ratings,
        BONDTYPE=bondtype,
        BONDTYPE43=bondtype43,
        COUPON_TYPE=None,
        COUPON_YIELD_TO_PRICE=bond.coupon_yield_to_price,
        COUPON_FREQUENCY=int(bond.coupon_frequency) if bond.coupon_frequency is not None else None,
        DURATION_YEARS=bond.duration_years,
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
    BondsRepository.select() для получения данных с применением всех фильтров на уровне БД.
    Преобразует сырые данные из БД в BondListItem, загружает данные о купонах,
    применяет фильтр по эмитенту (если указан), и возвращает BondsListResponse.
    
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
        - bonds: Список объектов BondListItem с данными облигаций.
    
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

    bonds = []
    for bond in bond_rows:
        try:
            bonds.append(_bond_to_list_item(bond, type_rev, kind_rev))
        except Exception:
            continue

    # Получаем значения ближайших купонов через CouponService
    current_date = date.today()
    secids = [b.SECID for b in bonds if b.SECID]
    coupons_map = get_coupon_service().get_nearest_coupon_values(
        secids=secids,
        from_date=current_date,
    )
    
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
