"""Утилита валидации и нормализации ответа LLM перед приведением к GeminiBondAnalysisDTO.

Приводит корневую структуру JSON к разрешённым секциям (issuer, instrument,
float_params, trading, calculation_engine). При падении валидации подставляет
fallback_inn в issuer.inn и base_indicator_code в float_params, затем повторяет валидацию.
"""

import logging
from typing import Any, Dict, Optional

from pydantic import ValidationError

from app.models.schemasDTO.gemini_dto import GeminiBondAnalysisDTO

logger: logging.Logger = logging.getLogger(__name__)

# Разрешённые корневые ключи ответа LLM (остальные отбрасываются).
ALLOWED_ROOT_KEYS: frozenset[str] = frozenset({
    "issuer",
    "instrument",
    "float_params",
    "trading",
    "calculation_engine",
})


def normalize_root_structure(parsed: Dict[str, Any]) -> Dict[str, Any]:
    """Оставляет в словаре только разрешённые корневые ключи.

    Args:
        parsed: Сырой словарь ответа LLM.

    Returns:
        Копия с ключами только из ALLOWED_ROOT_KEYS.
    """
    return {k: v for k, v in parsed.items() if k in ALLOWED_ROOT_KEYS}


def _apply_fallback_substitutions(
    data: Dict[str, Any],
    fallback_inn: Optional[str],
) -> None:
    """Подставляет fallback-значения в data (in-place).

    - issuer.inn: если None или отсутствует и задан fallback_inn.
    (base_indicator_code задаётся значением по умолчанию в GeminiFloatParamsDTO.)
    """
    if fallback_inn is not None:
        issuer = data.get("issuer")
        if isinstance(issuer, dict) and issuer.get("inn") is None:
            issuer["inn"] = fallback_inn


def validate_analysis_response(
    parsed: Dict[str, Any],
    fallback_inn: Optional[str] = None,
) -> Optional[GeminiBondAnalysisDTO]:
    """Валидирует ответ LLM и при необходимости подставляет fallback с повторной валидацией.

    1. Нормализует корень (только разрешённые ключи).
    2. Пытается собрать GeminiBondAnalysisDTO.
    3. При ValidationError подставляет fallback_inn в issuer.inn, затем повторяет валидацию.
       (base_indicator_code при null задаётся в модели значением по умолчанию "NA".)

    Args:
        parsed: Разобранный JSON ответа модели.
        fallback_inn: ИНН из БД (до пайплайна), подставляется в issuer.inn при ошибке валидации.

    Returns:
        Валидированный DTO или None при неуспешной валидации после подстановок.
    """
    data: Dict[str, Any] = normalize_root_structure(parsed)

    try:
        return GeminiBondAnalysisDTO(**data)
    except ValidationError as exc:
        logger.warning(
            "[LLM VALIDATION] Первая попытка не прошла (%d ошибок), применяю подстановки: %s",
            exc.error_count(),
            exc,
        )
        for err in exc.errors():
            loc: str = ".".join(str(x) for x in err.get("loc", ()))
            logger.debug("  — поле %r: %s", loc, err.get("msg", ""))
        _apply_fallback_substitutions(data, fallback_inn)
        try:
            return GeminiBondAnalysisDTO(**data)
        except ValidationError as retry_exc:
            logger.warning(
                "[LLM VALIDATION] Повторная валидация не прошла (%d ошибок): %s",
                retry_exc.error_count(),
                retry_exc,
            )
            for err in retry_exc.errors():
                loc = ".".join(str(x) for x in err.get("loc", ()))
                logger.debug("  — поле %r: %s", loc, err.get("msg", ""))
            return None
