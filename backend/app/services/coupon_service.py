"""Сервис-оркестратор для работы с данными о купонах облигаций.

Модуль содержит класс CouponService, координирующий загрузку данных из API MOEX,
файлового хранилища и базы данных. Отвечает за бизнес-логику обновления и
предоставления данных о купонах.
"""

from datetime import date, datetime
from pathlib import Path
from typing import Dict, List, Optional

from app.repository.db.db_coupon import DBCoupon
from app.repository.files.file_storage import FileStorage
from app.services.coupon_loader import get_coupon_loader
from app.services.data_loader import get_data_loader
from app.services.moex_client import MoexClient
from app.utils.coupon_utils import to_frontend_coupon
from config.paths import DATA_DIR as COUPONS_DATA_DIR


class CouponService:
    """Сервис-оркестратор для работы с данными о купонах облигаций.

    Координирует загрузку данных из API MOEX, файлового хранилища и БД.
    Решает, нужна ли загрузка с MOEX, сохраняет данные в JSON и обеспечивает
    предоставление актуальных данных через get_coupons и get_coupons_batch.

    Attributes:
        STALE_DAYS: Количество дней, после которых данные считаются устаревшими.
    """

    STALE_DAYS: int = 14

    def __init__(
        self,
        data_dir: Path = COUPONS_DATA_DIR,
        moex_client: Optional[MoexClient] = None,
        file_storage: Optional[FileStorage] = None,
    ):
        """Инициализирует сервис купонов.

        Args:
            data_dir: Директория с файлами данных.
            moex_client: Клиент MOEX (создается при отсутствии).
            file_storage: Хранилище файлов (создается при отсутствии).
        """
        self._moex_client = moex_client or MoexClient()
        self._file_storage = file_storage or FileStorage()
        from config.paths import COUPONS_DATA_JSON
        self._coupons_path = Path(data_dir) / COUPONS_DATA_JSON
        self._file_storage.ensure_coupons_exists(self._coupons_path)

    def _is_data_stale(self, last_updated: str) -> bool:
        """Проверяет, устарели ли данные.

        Args:
            last_updated: Дата последнего обновления (YYYY-MM-DD).

        Returns:
            True если данные старше STALE_DAYS дней, иначе False.
            При некорректной дате возвращает True.
        """
        try:
            last_date = datetime.strptime(last_updated, "%Y-%m-%d").date()
            return (date.today() - last_date).days > self.STALE_DAYS
        except (ValueError, TypeError):
            return True

    def _fetch_bond_coupons_from_db(self, secid: str) -> Dict:
        """Получает данные о купонах облигации из базы данных.

        Returns:
            Словарь: last_updated, coupons, offers (пустой).
        """
        db_coupon = DBCoupon()
        rows = db_coupon.fetch_coupons_for_frontend(secids=[secid])
        coupons = [to_frontend_coupon(row) for row in rows]
        return {
            "last_updated": date.today().isoformat(),
            "coupons": coupons,
            "offers": [],
        }

    def get_coupons(self, secid: str, force_refresh: bool = False) -> Dict:
        """Получает данные о купонах для конкретной облигации.

        Проверяет актуальность данных в JSON. При необходимости загружает
        с MOEX, сохраняет в файл и синхронизирует кэши. Данные для ответа
        берутся из базы данных.

        Args:
            secid: Идентификатор облигации (SECID).
            force_refresh: При True принудительно загружает данные из API MOEX.

        Returns:
            Словарь с ключами: last_updated, coupons, offers.

        Raises:
            RuntimeError: Если не удалось загрузить данные из API и в БД нет данных.
        """
        data = self._file_storage.read_coupons(self._coupons_path)
        bonds = data.get("bonds", {})

        if secid in bonds and not force_refresh:
            bond_data = bonds[secid]
            last_updated = bond_data.get("last_updated", "")
            if last_updated and not self._is_data_stale(last_updated):
                return self._fetch_bond_coupons_from_db(secid)

        try:
            fresh_data = self._moex_client.fetch_coupons(secid)
        except Exception as exc:
            try:
                return self._fetch_bond_coupons_from_db(secid)
            except Exception:
                raise exc from exc

        bond_entry = {
            "last_updated": date.today().isoformat(),
            "amortizations": fresh_data["amortizations"],
            "coupons": fresh_data["coupons"],
            "offers": fresh_data["offers"],
        }
        bonds[secid] = bond_entry
        data["bonds"] = bonds
        self._file_storage.write_coupons(self._coupons_path, data)

        coupon_loader = get_coupon_loader()
        if coupon_loader is not None:
            coupon_loader.clear_cache()

        try:
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

        Args:
            secids: Список идентификаторов облигаций (SECID).
            use_db: Должен быть True. Данные берутся только из БД.

        Returns:
            Словарь: ключ — SECID, значение — {"coupons": [...]}.

        Raises:
            ValueError: Если use_db=False.
        """
        if not secids:
            return {}

        if not use_db:
            raise ValueError("Данные о купонах доступны только из базы данных")

        db_coupon = DBCoupon()
        rows = db_coupon.fetch_coupons_for_frontend(secids=secids)

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
            from_date: Начальная дата для фильтрации (выбираются купоны с
                coupondate >= from_date). Если None, используется текущая дата.

        Returns:
            Словарь: ключ — SECID, значение — сумма купона (float) или None,
            если купон не найден или значение отсутствует.
            При пустом secids или ошибке доступа к БД возвращает пустой словарь.
        """
        if not secids:
            return {}

        effective_date = from_date or date.today()
        from_date_str = effective_date.isoformat()

        try:
            db_coupon = DBCoupon()
            rows = db_coupon.fetch_coupons_raw(
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

        Выбирает купон с минимальной датой (coupondate >= current_date),
        так как фильтрация по from_date уже выполнена на уровне БД.

        Args:
            coupons: Список словарей с данными купонов. Каждый словарь содержит
                поле coupondate в формате YYYY-MM-DD.
            current_date: Текущая дата. Список уже отфильтрован (купоны >= current_date).

        Returns:
            Словарь с данными ближайшего будущего купона или None, если список пуст.
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
