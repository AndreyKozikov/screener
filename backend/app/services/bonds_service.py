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

import sqlite3
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import orjson

from app.models.bond import BondListItem
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


def _row_to_bond_list_item(
    row: Dict[str, Any],
    type_rev: Dict[int, str],
    kind_rev: Dict[int, str],
) -> BondListItem:
    """Преобразует сырую строку из БД в объект BondListItem.
    
    Выполняет преобразование данных облигации из формата базы данных (словарь)
    в объект модели BondListItem. Вычисляет производные поля (coupon_period из
    coupon_frequency, duration_days из duration_years) и применяет обратные маппинги
    для преобразования ID типов и видов облигаций в строковые значения.
    
    Args:
        row: Словарь с данными облигации из таблицы bonds. Должен содержать все
            необходимые поля таблицы (secid, name, rating, current_price, и т.д.).
        type_rev: Обратный маппинг типов облигаций (ID -> строка).
        kind_rev: Обратный маппинг видов облигаций (ID -> строка).
    
    Returns:
        Объект BondListItem с данными облигации, готовый для использования в API.
    """
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
        COUPONPERCENT=float(row.get("coupon_percent")) if row.get("coupon_percent") is not None else None,
        MATDATE=maturity_date,
        STATUS=None,
        TRADINGSTATUS=None,
        FACEVALUE=float(row.get("face_value")) if row.get("face_value") is not None else None,
        PREVPRICE=float(row.get("current_price")) if row.get("current_price") is not None else None,
        YIELDATPREVWAPRICE=float(row.get("yield_to_maturity")) if row.get("yield_to_maturity") is not None else None,
        NEXTCOUPON=None,
        BOARDNAME=None,
        CALLOPTIONDATE=None,
        PUTOPTIONDATE=None,
        ACCRUEDINT=float(row.get("accrued_interest")) if row.get("accrued_interest") is not None else None,
        COUPONPERIOD=coupon_period,
        COUPONVALUE=float(row.get("coupon_value")) if row.get("coupon_value") is not None else None,
        DURATION=duration_days,
        DURATIONWAPRICE=None,
        CURRENCYID=str(row.get("currency") or "").strip() or None,
        FACEUNIT=str(row.get("currency") or "").strip() or None,
        LISTLEVEL=int(row.get("listing_level")) if row.get("listing_level") is not None else None,
        RATING_AGENCY=None,
        RATING_LEVEL=rating,
        RATINGS=ratings,
        BONDTYPE=bondtype,
        BONDTYPE43=bondtype43,
        COUPON_TYPE=None,
        COUPON_YIELD_TO_PRICE=float(row.get("coupon_yield_to_price")) if row.get("coupon_yield_to_price") is not None else None,
        COUPON_FREQUENCY=int(row.get("coupon_frequency")) if row.get("coupon_frequency") is not None else None,
        DURATION_YEARS=float(row.get("duration_years")) if row.get("duration_years") is not None else None,
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
        backend = Path(__file__).resolve().parent.parent.parent
        data_dir = backend / "app" / "data"
    data_dir = Path(data_dir)

    type_rev, kind_rev = _load_mappings(data_dir)

    db = BondsRepository(db_path=db_path)

    # Используем универсальный метод select, который применяет все фильтры на уровне БД
    # Фронтенд теперь отправляет ID напрямую, преобразование не требуется
    # bondtype и bondtype43 уже содержат ID (числа), которые передаются напрямую в SQL-запрос
    try:
        raw = db.select(
            filters=filters,
            bond_type_ids=filters.bondtype,
            bond_kind_ids=filters.bondtype43,
            exclude_spob=exclude_spob,
        )
    except sqlite3.OperationalError as e:
        # Если таблица не существует, возвращаем пустой список
        # Это может произойти, если база данных не была инициализирована
        if "no such table" in str(e).lower() or "no such table: bonds" in str(e).lower():
            raw = []
        else:
            raise
    
    # total — число всех облигаций в БД (без фильтров), для совместимости с API
    try:
        total = db.count_bonds(exclude_spob=False)
    except sqlite3.OperationalError as e:
        # Если таблица не существует, возвращаем 0
        if "no such table" in str(e).lower() or "no such table: bonds" in str(e).lower():
            total = 0
        else:
            raise

    # Преобразуем в BondListItem
    bonds: List[BondListItem] = []
    for r in raw:
        try:
            bonds.append(_row_to_bond_list_item(r, type_rev, kind_rev))
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
