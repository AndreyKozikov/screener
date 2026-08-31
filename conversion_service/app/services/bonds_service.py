import sqlite3
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
import httpx

from conversion_service.app.models.bonds_data_dto import BondsDataDTO
from conversion_service.app.utils.rating_utils import get_rating_index, standardize_rating
from config.paths import DB_PATH
from db_repository.models.bond import Bond


def get_emitent_inn_by_secid(secid: str, db_path: Optional[Path] = None) -> Optional[str]:
    path = db_path or DB_PATH
    if not path.exists():
        return None

    query = """
        SELECT e.inn
        FROM bonds b
        JOIN emitents e ON b.emitent_id = e.id
        WHERE b.secid = ?
    """
    try:
        with sqlite3.connect(path) as conn:
            cursor = conn.cursor()
            cursor.execute(query, (secid,))
            row = cursor.fetchone()
            return row[0] if row else None
    except Exception:
        return None


def get_reg_number_by_secid(secid: str, db_path: Optional[Path] = None) -> Optional[str]:
    path = db_path or DB_PATH
    if not path.exists():
        return None

    query = """
        SELECT bs.reg_number
        FROM bonds b
        JOIN bondsecurity bs ON bs.bond_id = b.id
        WHERE b.secid = ? 
            AND bs.reg_number IS NOT NULL AND trim(bs.reg_number) != ''
            AND (b.boardid IS NULL OR UPPER(TRIM(b.boardid)) != 'PACT')
    """
    try:
        with sqlite3.connect(path) as conn:
            cursor = conn.cursor()
            cursor.execute(query, (secid,))
            row = cursor.fetchone()
            return row[0] if row else None
    except Exception:
        return None


def get_floater_secids(db_path: Optional[Path] = None, rating: Optional[str] = None) -> List[str]:
    path = db_path or DB_PATH
    if not path.exists():
        return []

    query = """
        SELECT secid 
        FROM bonds 
        WHERE bond_kind = 8 
          AND bond_type IS NOT NULL 
          AND bond_type NOT IN (2, 4, 5)
          AND (boardid IS NULL OR UPPER(TRIM(boardid)) != 'PACT')
    """
    params = []

    if rating and rating.strip():
        query += " AND UPPER(TRIM(rating)) = ?"
        params.append(rating.strip().upper())

    try:
        with sqlite3.connect(path) as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            rows = cursor.fetchall()
            return [row[0] for row in rows]
    except Exception:
        return []


def get_all_bond_secids() -> List[str]:
    pass



def get_all_bonds_metadata(
        db_path: Optional[Path] = None, rating: Optional[str] = None
) -> Dict[str, Tuple[str, str]]:
    """Returns a dict mapping secid to (inn, reg_number) for all bonds with registration numbers."""
    path = db_path or DB_PATH
    if not path.exists():
        return {}

    query = """
        SELECT b.secid, trim(e.inn), trim(bs.reg_number)
        FROM bonds b
        JOIN bondsecurity bs ON bs.bond_id = b.id
        JOIN emitents e ON b.emitent_id = e.id
        WHERE bs.reg_number IS NOT NULL AND trim(bs.reg_number) != ''
          AND (b.boardid IS NULL OR UPPER(TRIM(b.boardid)) != 'PACT')
    """
    params = []

    if rating and rating.strip():
        query += " AND UPPER(TRIM(b.rating)) = ?"
        params.append(rating.strip().upper())

    try:
        with sqlite3.connect(path) as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            rows = cursor.fetchall()
            return {
                str(row[0]).strip(): (str(row[1]).strip(), str(row[2]).strip())
                for row in rows
                if row[0] and row[1] and row[2]
            }
    except Exception:
        return {}


from conversion_service.app.utils.moex_loader import get_moex_loader
from conversion_service.app.core.bond_transformer import BondTransformer


class BondsUpdateService:

    def __init__(self):
        self.MOEX_BONDS_URL: str = (
            "https://iss.moex.com/iss/engines/stock/markets/bonds/securities.json"
        )
        self.moex = get_moex_loader()
        self.bond_transformer = BondTransformer()

    async def update_bonds_data(self):
        payload = self.moex.bonds_data_load(self.MOEX_BONDS_URL)
        raw_bonds_data = self.bond_transformer.transform_raw_payload(payload)
        secids = list(raw_bonds_data.keys())
        bonds_rating_map = await self._load_ratings_map()
        emitents_rating_map = await self._load_emitent_map()

        current_coupon = await self._load_current_coupons(secids)

        print("=============================================================")
        type_mapping, kind_mapping = self.bond_transformer.load_mappings()

        for secid, bond_data in raw_bonds_data.items():
            bond_data["securities"]["RATING_AGENCY"] = ""
            bond_data["securities"]["RATING_LEVEL"] = ""
            ratings = []
            # 1) Рейтинг: сначала из bond_ratings (БД)
            if secid in bonds_rating_map:
                ratings = bonds_rating_map[secid].get("all_ratings", [])

            # 2) Если рейтинг не установлен — из emitent_ratings по эмитенту (БД)
            if secid in emitents_rating_map:
                emitent_entry = emitents_rating_map[secid]
                bond_type_str = emitent_entry.get("type")
                bond_data["securities"]["BONDTYPE"] = type_mapping.get(bond_type_str)

                if not ratings:
                    ratings = emitent_entry.get("cci_rating_companies", []) or []

            # 3) Стандартизация рейтинга и запись в структуру для сохранения в БД
            if ratings:
                worst_rating = self._get_worst_rating(ratings)

                if worst_rating:
                    bond_data["securities"]["RATING_AGENCY"] = worst_rating.get("agency_name_short_ru", "").strip()
                    rating_level_raw = worst_rating.get("rating_level_name_short_ru", "").strip()
                    bond_data["securities"]["RATING_LEVEL"] = standardize_rating(rating_level_raw) or rating_level_raw

            bond_kind_str = bond_data["securities"].get("BONDTYPE43")
            bond_data["securities"]["BONDTYPE43"] = kind_mapping.get(bond_kind_str)
            coupon_period = bond_data["securities"]["COUPONPERIOD"]
            current_price = bond_data["marketdata"]["LCURRENTPRICE"]
            coupon_value = current_coupon.get(secid)
            face_value = bond_data["securities"]["FACEVALUE"]

            if (
                    coupon_value is not None
                    and current_price is not None
                    and face_value is not None
                    and coupon_period
                    and coupon_period > 0
            ):
                try:
                    payments_per_year = 365 / coupon_period
                    if current_price > 0 and face_value > 0:
                        coupon_yield_to_price = (
                                (coupon_value * 10000 / (current_price * face_value)) * payments_per_year
                        )
                except (ZeroDivisionError, TypeError):
                    coupon_yield_to_price = 0
            bond_data["securities"]["COUPONYIELDTOPRICE"] = coupon_yield_to_price

        bonds_data_dto = BondsDataDTO.model_validate(raw_bonds_data)
        try:
            async with httpx.AsyncClient(timeout=600) as client:
                response = await client.post(
                    url="http://127.0.0.1:8964/api/bonds_data_update",
                    json=bonds_data_dto.model_dump(by_alias=False),
                    headers={"Content-Type": "application/json"},
                )
                response.raise_for_status()
                return response.json()
        except Exception as e:
            raise

    async def _load_current_coupons(self, secids: List[str]):

        try:
            async with httpx.AsyncClient(timeout=600) as client:
                response = await client.post(
                    url="http://127.0.0.1:8964/api/coupons/current_coupon",
                    json=secids,
                    headers={"Content-Type": "application/json"},
                )
                response.raise_for_status()
                result = response.json()
        except Exception as e:
            raise
        return result

    async def _load_ratings_map(self) -> Dict[str, Dict[str, List[Dict[str, Any]]]]:
        """Загружает рейтинги облигаций из БД (bond_ratings + bonds + rating_agency).

        Один запрос с JOIN: bonds.secid, rating_agency.agency_name_short_ru,
        bond_ratings.rating_level_name. Для secid без рейтингов в словаре записи нет
        (при обращении вернуть пустой список).

        Returns:
            Словарь: ключ — secid, значение — {"all_ratings": [{"agency_name_short_ru", "rating_level_name", "rating_level_name_short_ru"}, ...]}.
        """
        ratings_map: Dict[str, Dict[str, List[Dict[str, Any]]]] = {}
        try:
            async with httpx.AsyncClient(timeout=600) as client:
                response = await client.get(
                    url="http://127.0.0.1:8964/api/ratings/bonds_rating_map",
                    headers={"Content-Type": "application/json"},
                )
                response.raise_for_status()
                rows = response.json()

            for secid, agency_name_short_ru, rating_level_name in rows:
                if not secid:
                    continue
                name_ru = (agency_name_short_ru or "").strip()
                level = (rating_level_name or "").strip()
                if not name_ru:
                    continue
                entry = {
                    "agency_name_short_ru": name_ru,
                    "rating_level_name": level,
                    "rating_level_name_short_ru": level,
                }
                if secid not in ratings_map:
                    ratings_map[secid] = {"all_ratings": []}
                ratings_map[secid]["all_ratings"].append(entry)
        except Exception as e:
            raise
        return ratings_map

    async def _load_emitent_map(self) -> Dict[str, Dict[str, Any]]:
        """Загружает данные эмитентов из БД (bonds -> emitents -> emitent_ratings -> rating_agency).

        Один запрос с JOIN по secid. Извлекает type из emitents, cci_rating_companies —
        список словарей с agency_name_short_ru и rating_level_name_short_ru для совместимости
        с _get_worst_rating.

        Returns:
            Словарь: ключ — secid, значение — {"type": str|None, "cci_rating_companies": [...]}.
        """
        emitent_map: Dict[str, Dict[str, Any]] = {}
        try:
            async with httpx.AsyncClient(timeout=600) as client:
                response = await client.get(
                    url="http://127.0.0.1:8964/api/ratings/emitents_rating_map",
                    headers={"Content-Type": "application/json"},
                )
                response.raise_for_status()
                rows = response.json()

            for secid, emitent_type, agency_name_short_ru, rating_level_name in rows:
                if not secid:
                    continue
                name_ru = (agency_name_short_ru or "").strip()
                level = (rating_level_name or "").strip() if rating_level_name else ""
                if secid not in emitent_map:
                    type_val = (emitent_type or "").strip() or None
                    emitent_map[secid] = {"type": type_val, "cci_rating_companies": []}
                emitent_map[secid]["cci_rating_companies"].append({
                    "agency_name_short_ru": name_ru,
                    "rating_level_name_short_ru": level,
                })
        except Exception as e:
            raise
        return emitent_map

    def _get_worst_rating(self, ratings_list: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Определяет наихудший рейтинг из списка рейтингов.

        Args:
            ratings_list: Список словарей с рейтингами.

        Returns:
            Словарь с наихудшим рейтингом или None.
        """
        if not ratings_list:
            return None
        non_revoked = [
            r for r in ratings_list
            if isinstance(r, dict)
               and (r.get("rating_level_name_short_ru") or "").lower() not in ("отозван", "отозвано")
        ]
        ratings_to_check = non_revoked if non_revoked else ratings_list
        if not ratings_to_check:
            return None
        worst_rating = None
        worst_index = -1
        for rating in ratings_to_check:
            level = (rating.get("rating_level_name_short_ru") or "").strip()
            if not level:
                continue
            idx = get_rating_index(level)
            if idx is not None and idx > worst_index:
                worst_index = idx
                worst_rating = rating
        return worst_rating


bonds_update_service: Optional[BondsUpdateService] = None


def get_bonds_update_service():
    global bonds_update_service
    if bonds_update_service is None:
        bonds_update_service = BondsUpdateService()
    return bonds_update_service
