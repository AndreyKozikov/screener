"""Сервис-оркестратор для работы с данными о купонах облигаций.

Модуль содержит класс CouponService, координирующий загрузку данных из API MOEX
и базы данных. Единственный источник истины для купонов — таблица coupons;
чтение и запись только через DBCoupon.
"""

from datetime import date, datetime
from typing import Dict, List, Optional

from app.repository.db.bonds_repository import BondsRepository
from app.repository.db.db_coupon import DBCoupon
from app.services.moex_client import MoexClient
from app.utils.coupon_utils import to_frontend_coupon
from config.paths import DB_PATH


class CouponService:
    """Сервис-оркестратор для работы с данными о купонах облигаций.

    Координирует загрузку данных из API MOEX и БД. Проверка актуальности —
    по наличию записей в таблице coupons для secid. Запись только через
    DBCoupon.save_coupons_bulk после получения данных из API.
    """

    def __init__(
        self,
        moex_client: Optional[MoexClient] = None,
    ):
        """Инициализирует сервис купонов.

        Args:
            moex_client: Клиент MOEX (создается при отсутствии).
        """
        self._moex_client = moex_client or MoexClient()
        self._db_coupon = DBCoupon(db_path=str(DB_PATH))
        self._bonds_repo = BondsRepository(db_path=DB_PATH)

    def _fetch_bond_coupons_from_db(self, secid: str) -> Dict:
        """Получает данные о купонах облигации из базы данных.

        Returns:
            Словарь: last_updated, coupons, offers (пустой).
        """
        rows = self._db_coupon.fetch_coupons_for_frontend(secids=[secid])
        coupons = [to_frontend_coupon(row) for row in rows]
        return {
            "last_updated": date.today().isoformat(),
            "coupons": coupons,
            "offers": [],
        }

    def get_coupons(self, secid: str, force_refresh: bool = False) -> Dict:
        """Получает данные о купонах для конкретной облигации.

        Проверяет наличие данных в БД (таблица coupons). Если данных нет или
        force_refresh — загружает с MOEX, сохраняет через DBCoupon.save_coupons_bulk
        и возвращает данные из БД.

        Args:
            secid: Идентификатор облигации (SECID).
            force_refresh: При True принудительно загружает данные из API MOEX.

        Returns:
            Словарь с ключами: last_updated, coupons, offers.

        Raises:
            RuntimeError: Если не удалось загрузить данные из API и в БД нет данных.
        """
        if not force_refresh and self._db_coupon.has_coupons_for_secid(secid):
            return self._fetch_bond_coupons_from_db(secid)

        try:
            fresh_data = self._moex_client.fetch_coupons(secid)
        except Exception as exc:
            if self._db_coupon.has_coupons_for_secid(secid):
                return self._fetch_bond_coupons_from_db(secid)
            raise RuntimeError(f"Не удалось загрузить купоны для {secid} и в БД нет данных") from exc

        bond_id = self._bonds_repo.get_bond_id_by_secid(secid)
        if bond_id is None:
            if self._db_coupon.has_coupons_for_secid(secid):
                return self._fetch_bond_coupons_from_db(secid)
            raise RuntimeError(f"Облигация {secid} не найдена в таблице bonds")

        records: List[Dict] = []
        for c in fresh_data.get("coupons", []):
            raw = {"bond_id": bond_id, **c}
            rec = self._db_coupon._transform_coupon_data(raw)
            if rec:
                records.append(rec)
        if records:
            self._db_coupon.save_coupons_bulk(records)

        try:
            from app.services.data_loader import get_data_loader
            get_data_loader().clear_bonds_cache()
        except RuntimeError:
            pass

        return self._fetch_bond_coupons_from_db(secid)

    def get_coupons_only(
        self, secid: str, force_refresh: bool = False
    ) -> List[Dict]:
        """Возвращает только список купонов для отображения на фронтенде.

        Args:
            secid: Идентификатор облигации (SECID).
            force_refresh: При True принудительно загружает данные из API MOEX.

        Returns:
            Список словарей с данными купонов.
        """
        bond_data = self.get_coupons(secid, force_refresh)
        return bond_data.get("coupons", [])

    def get_coupons_batch(
        self, secids: List[str], use_db: bool = True
    ) -> Dict[str, Dict]:
        """Получает данные о купонах для нескольких облигаций из БД.

        Один SQL-запрос к DBCoupon с фильтром WHERE secid IN (...).

        Args:
            secids: Список идентификаторов облигаций (SECID).
            use_db: Должен быть True. Оставлен для совместимости.

        Returns:
            Словарь: ключ — SECID, значение — {"coupons": [...]}.

        Raises:
            ValueError: Если use_db=False.
        """
        if not secids:
            return {}

        if not use_db:
            raise ValueError("Данные о купонах доступны только из базы данных")

        rows = self._db_coupon.fetch_coupons_for_frontend(secids=secids)
        coupons_by_secid: Dict[str, List[Dict]] = {s: [] for s in secids}
        for row in rows:
            sid = row.get("secid")
            if sid and sid in coupons_by_secid:
                coupons_by_secid[sid].append(to_frontend_coupon(row))
        return {sid: {"coupons": coupons_by_secid[sid]} for sid in secids}

    def get_nearest_coupon_values(
        self,
        secids: List[str],
        from_date: Optional[date] = None,
    ) -> Dict[str, Optional[float]]:
        """Возвращает значение ближайшего будущего купона для каждой облигации.

        Для каждой облигации из списка secids запрашивает купоны с датой выплаты
        не ранее from_date, выбирает купон с наиболее близкой датой и возвращает
        значение поля value.

        Args:
            secids: Список идентификаторов облигаций (SECID) для получения купонов.
            from_date: Начальная дата для фильтрации (купоны с coupondate >= from_date).
                Если None, используется текущая дата.

        Returns:
            Словарь: ключ — SECID, значение — сумма купона (float) или None.
            При пустом secids или ошибке доступа к БД возвращает пустой словарь.
        """
        if not secids:
            return {}

        effective_date = from_date or date.today()
        from_date_str = effective_date.isoformat()

        try:
            rows = self._db_coupon.fetch_coupons_raw(
                secids=secids,
                from_date=from_date_str,
            )
        except Exception:
            return {}

        coupons_by_secid: Dict[str, List[Dict]] = {}
        for row in rows:
            sid = row.get("secid")
            if sid:
                if sid not in coupons_by_secid:
                    coupons_by_secid[sid] = []
                coupons_by_secid[sid].append(row)

        result: Dict[str, Optional[float]] = {}
        for sid in secids:
            coupons = coupons_by_secid.get(sid, [])
            closest = self._find_closest_future_coupon(coupons, effective_date)
            if closest is not None:
                val = closest.get("value")
                if val is not None:
                    try:
                        result[sid] = float(val)
                    except (ValueError, TypeError):
                        result[sid] = None
                else:
                    result[sid] = None
            else:
                result[sid] = None

        return result

    def _find_closest_future_coupon(
        self,
        coupons: List[Dict],
        current_date: date,
    ) -> Optional[Dict]:
        """Находит будущий купон с наиболее близкой датой выплаты.

        Args:
            coupons: Список словарей с данными купонов (поле coupondate YYYY-MM-DD).
            current_date: Текущая дата. Список уже отфильтрован (купоны >= current_date).

        Returns:
            Словарь ближайшего будущего купона или None.
        """
        if not coupons:
            return None
        closest = None
        min_date = None
        for coupon in coupons:
            cd_str = coupon.get("coupondate")
            if not cd_str:
                continue
            try:
                cd = date.fromisoformat(cd_str)
                if min_date is None or cd < min_date:
                    min_date = cd
                    closest = coupon
            except (ValueError, TypeError):
                continue
        return closest


_coupon_service: Optional[CouponService] = None


def get_coupon_service() -> CouponService:
    """Возвращает singleton экземпляр сервиса купонов.

    Returns:
        Экземпляр CouponService для работы с данными о купонах.
    """
    global _coupon_service
    if _coupon_service is None:
        _coupon_service = CouponService()
    return _coupon_service
