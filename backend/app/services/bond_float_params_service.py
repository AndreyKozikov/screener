"""Сервис для предоставления параметров плавающей процентной ставки облигаций.

Обеспечивает формирование объектов BondFloatParamsDTO, объединяя основные данные
облигации и специфические условия доходности (флоатеры), извлеченные из документов.
"""

import logging
from datetime import date
from typing import List, Optional

from db_repository.models.bond import Bond
from app.models.entities.bond_float_params import BondFloatParams
from app.models.schemasDTO.bond_float_params_dto import BondFloatParamsDTO
from app.repository.db.bond_float_params_repository import BondFloatParamsRepository
from app.repository.db.bonds_repository import BondsRepository


class BondFloatParamsService:
    """Сервис управления параметрами флоатеров.

    Координирует взаимодействие между репозиториями облигаций и параметров флоатеров.
    Выполняет расчет вспомогательных метрик, таких как количество дней до погашения.

    Attributes:
        _bonds_repo (BondsRepository): Репозиторий для работы с основными данными облигаций.
        _float_repo (BondFloatParamsRepository): Репозиторий для работы с параметрами флоатеров.
        _logger (Logger): Объект для ведения журналов событий.
    """

    def __init__(self, bonds_repo: BondsRepository, float_repo: BondFloatParamsRepository) -> None:
        """Инициализирует сервис с необходимыми репозиториями.

        Args:
            bonds_repo (BondsRepository): Репозиторий для работы с основными данными облигаций.
            float_repo (BondFloatParamsRepository): Репозиторий для работы с параметрами флоатеров.
        """
        self._bonds_repo = bonds_repo
        self._float_repo = float_repo
        self._logger = logging.getLogger(__name__)

    @staticmethod
    def _compute_days_to_maturity(maturity_date_str: Optional[str]) -> Optional[int]:
        """Вычисляет количество дней от текущей даты до даты погашения.

        Args:
            maturity_date_str (Optional[str]): Дата погашения в формате ISO (строка).

        Returns:
            Optional[int]: Положительное количество дней или None, если дата отсутствует,
                некорректна или погашение уже наступило.
        """
        if not maturity_date_str or not maturity_date_str.strip():
            return None
        try:
            mat = date.fromisoformat(maturity_date_str.strip()[:10])
            delta = (mat - date.today()).days
            return delta if delta >= 0 else None
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _build_dto(
        float_params: BondFloatParams,
        bond: Bond,
        days_to_maturity: Optional[int],
    ) -> BondFloatParamsDTO:
        """Собирает объект BondFloatParamsDTO на основе сущностей Bond и BondFloatParams.

        Args:
            float_params (BondFloatParams): Сущность с параметрами плавающей ставки.
            bond (Bond): Сущность облигации с базовыми данными.
            days_to_maturity (Optional[int]): Предварительно вычисленное число дней до погашения.

        Returns:
            BondFloatParamsDTO: Сформированный объект DTO для передачи данных.
        """
        return BondFloatParamsDTO(
            secid=bond.secid,
            name_short=bond.name,
            maturity_date=bond.maturity_date,
            nominal=bond.face_value,
            days_to_maturity=days_to_maturity,
            is_find=float_params.is_find,
            base_indicator_code=float_params.base_indicator_code,
            spread=float_params.spread,
            coupon_frequency_days=float_params.coupon_frequency_days,
            lookback_period=float_params.lookback_period,
            averaging_period=float_params.averaging_period,
            formula_raw=float_params.formula_raw,
            rate_determination_rule=float_params.rate_determination_rule,
            calculation_type=float_params.calculation_type,
            rounding_precision=float_params.rounding_precision,
            key_rate_method=float_params.key_rate_method,
            lookback_type=float_params.lookback_type,
            year_base=float_params.year_base,
            is_daily_accrual=float_params.is_daily_accrual,
            offset_days=float_params.offset_days,
            offset_calendar=float_params.offset_calendar,
            day_count=float_params.day_count,
            fallback=float_params.fallback,
            accrual_type=float_params.accrual_type,
            interest_compounding=float_params.interest_compounding,
            placement_date=float_params.placement_date,
            underwriter=float_params.underwriter,
            floor_rate=float_params.floor_rate,
            cap_rate=float_params.cap_rate,
            extra_indicators=float_params.extra_indicators,
            condition_logic=float_params.condition_logic,
            observation_type=float_params.observation_type,
            reference_period_desc=float_params.reference_period_desc,
        )

    def get_float_params_by_secid(self, secid: str) -> Optional[BondFloatParamsDTO]:
        """Возвращает параметры флоатера по его SECID.

        Args:
            secid (str): Идентификатор ценной бумаги (например, 'RU000A107TT9').

        Returns:
            Optional[BondFloatParamsDTO]: Объект DTO с параметрами или None,
                если облигация не найдена или для нее отсутствуют параметры флоатера.
        """
        bond_id = self._bonds_repo.get_bond_id_by_secid(secid)
        if bond_id is None:
            self._logger.debug("Bond not found for secid=%s", secid)
            return None

        float_params = self._float_repo.get_by_bond_id(bond_id)
        if float_params is None or float_params.is_find == 0:
            self._logger.debug(
                "Float params not found or is_find=0 for secid=%s (bond_id=%s)",
                secid,
                bond_id,
            )
            return None

        detail = self._bonds_repo.get_bond_detail_by_secid(secid)
        if detail is None:
            return None
        bond = detail[0]

        days_to_maturity = self._compute_days_to_maturity(bond.maturity_date)
        return self._build_dto(float_params, bond, days_to_maturity)

    def get_floater_secids_from_params(self) -> List[str]:
        """Возвращает список SECID всех облигаций, для которых успешно найдены параметры флоатера.

        Выбирает все bond_id из таблицы параметров, где флаг поиска установлен (is_find != 0),
        и преобразует их в SECID через репозиторий облигаций.

        Returns:
            List[str]: Список идентификаторов ценных бумаг. Пустой список, если данные не найдены.
        """
        bond_ids = self._float_repo.get_bond_ids_with_find()
        if not bond_ids:
            return []
        return self._bonds_repo.get_secids_by_ids(bond_ids)
