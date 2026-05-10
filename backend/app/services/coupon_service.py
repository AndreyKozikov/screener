"""Сервис-оркестратор для управления данными о купонах облигаций.

Координирует процессы получения графиков купонных выплат из API Московской Биржи (MOEX)
и их синхронизации с локальной базой данных. Обеспечивает единый интерфейс доступа
к купонной информации для других компонентов системы.
"""

from datetime import date, datetime
from typing import Dict, List, Optional

from app.repository.db.bonds_repository import BondsRepository
from app.repository.db.db_coupon import DBCoupon
from app.services.moex_client import MoexClient
from app.utils.coupon_utils import to_frontend_coupon
from config.paths import DB_PATH


class CouponService:
    """Оркестратор купонных данных.

    Класс инкапсулирует логику проверки актуальности данных в БД и, при необходимости,
    загрузки свежей информации через API. Гарантирует целостность данных за счет
    использования DBCoupon для всех операций записи.

    Attributes:
        _moex_client (MoexClient): Клиент для взаимодействия с API Московской Биржи.
        _db_coupon (DBCoupon): Репозиторий для работы с таблицей купонов.
        _bonds_repo (BondsRepository): Репозиторий для получения ID облигаций.
    """

    def __init__(
        self,
        moex_client: Optional[MoexClient] = None,
    ):
        """Инициализирует сервис купонов.

        Args:
            moex_client (Optional[MoexClient]): Клиент для запросов к MOEX ISS API.
                Если не указан, создается новый экземпляр MoexClient.
        """
        self._moex_client = moex_client or MoexClient()
        self._db_coupon = DBCoupon(db_path=str(DB_PATH))
        self._bonds_repo = BondsRepository(db_path=DB_PATH)

    def _fetch_bond_coupons_from_db(self, secid: str) -> Dict:
        """Извлекает историю купонных выплат для бумаги из базы данных.

        Args:
            secid (str): Идентификатор ценной бумаги (SECID).

        Returns:
            Dict: Словарь с датой обновления, списком купонов и оферт (для фронтенда).
        """
        rows = self._db_coupon.fetch_coupons_for_frontend(secids=[secid])
        coupons = [to_frontend_coupon(row) for row in rows]
        return {
            "last_updated": date.today().isoformat(),
            "coupons": coupons,
            "offers": [],
        }

    def get_coupons(self, secid: str, force_refresh: bool = False) -> Dict:
        """Получает полный график купонов для облигации.

        Если данные отсутствуют в БД или установлен флаг force_refresh, сервис
        обращается к API MOEX, обновляет базу и возвращает актуальный результат.

        Args:
            secid (str): Идентификатор ценной бумаги (SECID).
            force_refresh (bool): Если True, игнорировать кэш БД и загрузить данные из API.

        Returns:
            Dict: Структурированные данные о купонах и офертах.

        Raises:
            RuntimeError: Если данные невозможно получить ни из API, ни из базы.
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
        """Возвращает упрощенный список только купонных выплат.

        Args:
            secid (str): Идентификатор ценной бумаги (SECID).
            force_refresh (bool): Флаг принудительного обновления из API.

        Returns:
            List[Dict]: Список словарей, каждый из которых описывает одну купонную выплату.
        """
        bond_data = self.get_coupons(secid, force_refresh)
        return bond_data.get("coupons", [])

    def get_coupons_batch(
        self, secids: List[str], use_db: bool = True
    ) -> Dict[str, Dict]:
        """Пакетно получает данные о купонах для нескольких облигаций из базы данных.

        Оптимизирует количество запросов к БД за счет использования одного SQL-запроса
        для всего списка SECID.

        Args:
            secids (List[str]): Список идентификаторов ценных бумаг.
            use_db (bool): Флаг использования БД (всегда True для этого метода).

        Returns:
            Dict[str, Dict]: Словарь, где ключ — SECID, а значение — данные о купонах.

        Raises:
            ValueError: Если параметр use_db установлен в False.
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
        """Определяет размер ближайшей будущей купонной выплаты для списка облигаций.

        Полезно для расчета текущей доходности и отображения в таблице скринера.

        Args:
            secids (List[str]): Список идентификаторов облигаций (SECID).
            from_date (Optional[date]): Дата, начиная с которой искать купоны.
                Если не указана, используется текущая дата.

        Returns:
            Dict[str, Optional[float]]: Словарь {secid: сумма_купона}.
                Если купон не найден, значение будет равно None.
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
        """Находит купон с минимальной датой, большей или равной текущей.

        Args:
            coupons (List[Dict]): Список сырых данных о купонах.
            current_date (date): Дата отсечки.

        Returns:
            Optional[Dict]: Словарь с данными ближайшего купона или None.
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
    """Возвращает глобальный экземпляр (синглтон) сервиса купонов.

    Returns:
        CouponService: Настроенный экземпляр сервиса.
    """
    global _coupon_service
    if _coupon_service is None:
        _coupon_service = CouponService()
    return _coupon_service
