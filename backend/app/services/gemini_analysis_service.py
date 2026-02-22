"""Сервис анализа облигационных данных через Google Gemini API.

Принимает результат EdisclosureService.get_accrued_income_by_secid(),
объединяет события и Markdown-файлы, отправляет промт в Gemini
и возвращает структурированный результат (GeminiBondAnalysisDTO).
"""

import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Protocol

from google import genai
from google.genai import types
from pydantic import ValidationError

from app.models.schemasDTO.gemini_dto import GeminiBondAnalysisDTO
from app.repository.files.markdown_repository import MarkdownFileRepository
from config.settings import settings

logger: logging.Logger = logging.getLogger(__name__)

_DATA_DIR: Path = Path(__file__).resolve().parent.parent / "data"


class GeminiClientProtocol(Protocol):
    """Протокол транспортного клиента для Gemini API."""

    def generate(self, prompt: str) -> str:
        """Отправляет промт и возвращает текст ответа."""
        ...


class MarkdownRepositoryProtocol(Protocol):
    """Протокол репозитория для чтения Markdown-файлов."""

    def read_files(self, filenames: List[str]) -> str:
        """Читает и объединяет содержимое файлов."""
        ...

_PROMPT_TEMPLATE: str = """\
Роль: Ты — аналитик данных долгового рынка, специализирующийся на алгоритмической обработке эмиссионной документации (флоатеров).

Задача: Проанализировать текст событий (JSON) и приложенные Markdown-файлы. Извлечь параметры выпуска облигаций и вернуть строго валидный JSON.

Правила обработки данных (Data Normalization):
- Числа: Все процентные ставки и спреды пиши как float (через точку, без знака %). Пример: 1.2.
- Даты: Используй стандарт ISO 8601 (YYYY-MM-DD).
- Спред: Ищи значение S. Если в тексте указано "спред 120 б.п.", запиши как 1.2.
- Базовый индикатор: Приведи к стандарту: KEY_RATE (Ключевая ставка ЦБ), RUONIA, OIS, LIBOR.
- Метод расчета: Кратко классифицируй логику определения ставки (например, "Average" или "Lookback").
- Расчет купона (Daily Accrual): Если ставка купона меняется ежедневно (база + спред начисляются каждый день), укажи "calculation_type": "DAILY". Если ставка фиксируется на весь купонный период — "calculation_type": "FIXED". Если не определено — null.
- Округление: Найди в тексте количество знаков после запятой, применяемых при расчёте НКД и купона (например, "до 2 знаков" → 2). Запиши в "rounding_precision" как целое число. Если не указано — null.
- Специфика KEY_RATE: Если base_indicator_code == "KEY_RATE", уточни метод — "SPOT" (берётся ставка на конкретную дату) или "MA" (скользящее среднее за период). Запиши в "key_rate_method". Для других индикаторов — null.
- Определение даты (Lookback Type): Уточни в поле "lookback_type", являются ли дни отступа календарными или рабочими. Допустимые значения: "CALENDAR", "BUSINESS". Если не указано — null.
- База года: Извлеки из текста количество дней в году, используемое в формуле расчёта (360, 365, 366 или "ACTUAL"). Запиши в "year_base" как строку. Если не указано — null.
- Сложная формула (Daily Accrual): Если купон рассчитывается как сумма ежедневных начислений (каждый день по формуле база_i × спред / days_in_year), установи "is_daily_accrual": true. В остальных случаях — false.

Инструкция по заполнению блока calculation_engine (глоссарий флагов):
Заполняй блок, используя строго следующие значения:

offset_calendar:
  CALENDAR — календарные дни, включая выходные (например, "5-й день").
  BUSINESS — только рабочие дни (например, "5-й рабочий/банковский день").

day_count:
  ACT/365 — база 365 дней.
  ACT/366 — учёт високосного года (фактическое кол-во дней в году).
  30/360  — немецкий/американский стандарт (каждый месяц = 30 дней, год = 360).

fallback:
  PRECEDING — если на дату T-n нет ставки, брать за T-n-1, T-n-2 и т.д.
  FOLLOWING — брать следующую доступную ставку.

accrual_type:
  DAILY_ACCRUAL — НКД растёт ежедневно на основе актуальной на этот день ставки.
  FIXED_PERIOD  — ставка фиксируется один раз в начале купона на весь период.

interest_compounding: true — если есть капитализация/сложный процент; false — в остальных случаях.
offset_days: Количество дней отступа (lookback). Целое число или null.

JSON Structure:
{{
  "issuer": {{
    "name_short": "Краткое название",
    "inn": "Строка",
    "rating_ru": "Текущий кредитный рейтинг, если упомянут"
  }},
  "instrument": {{
    "isin": "Строка или null",
    "series": "Строка",
    "nominal": 1000.0,
    "maturity_date": "YYYY-MM-DD",
    "days_to_maturity": 1440
  }},
  "float_params": {{
    "base_indicator_code": "KEY_RATE | RUONIA | OTHER",
    "spread": 1.2,
    "coupon_frequency_days": 30,
    "lookback_period": 5,
    "averaging_period": 0,
    "formula_raw": "Чистая математическая формула из текста (LaTeX)",
    "rate_determination_rule": "Описание: за сколько дней и как фиксируется ставка",
    "calculation_type": "DAILY | FIXED | null",
    "rounding_precision": 2,
    "key_rate_method": "SPOT | MA | null",
    "lookback_type": "CALENDAR | BUSINESS | null",
    "year_base": "360 | 365 | 366 | ACTUAL | null",
    "is_daily_accrual": false
  }},
  "trading": {{
    "listing_level": 1,
    "placement_date": "YYYY-MM-DD",
    "underwriter": "Название организации"
  }},
  "calculation_engine": {{
    "offset_days": 5,
    "offset_calendar": "CALENDAR | BUSINESS | null",
    "day_count": "ACT/365 | ACT/366 | 30/360 | null",
    "fallback": "PRECEDING | FOLLOWING | null",
    "accrual_type": "DAILY_ACCRUAL | FIXED_PERIOD",
    "interest_compounding": false
  }}
}}

Инструкция по приоритетам:
- Сначала ищи значение спреда в events (событиях), так как там публикуются финальные итоги сбора заявок.
- Формулу и правила фиксации (lookback) бери из "Решения о выпуске" или "ДСУР".
- Если данных о спреде нет, напиши null, не выдумывай число.

Входные данные для анализа:
EVENTS (JSON):
{events_json}

MARKDOWN ДОКУМЕНТЫ:
{markdown_content}"""


class GeminiClient:
    """Клиент для обращения к Google Gemini API.

    Инкапсулирует инициализацию модели и отправку запросов,
    отделяя транспортный слой от бизнес-логики сервиса.
    """

    def __init__(self, api_key: str) -> None:
        """Настраивает Gemini SDK и создаёт клиент.

        Args:
            api_key: Ключ API Google Gemini.
        """
        self._client: genai.Client = genai.Client(api_key=api_key)
        self._config: types.GenerateContentConfig = types.GenerateContentConfig(
            temperature=0.1,
        )

    def generate(self, prompt: str) -> str:
        """Отправляет промт в Gemini и возвращает текст ответа.

        Args:
            prompt: Полный текст промта.

        Returns:
            Текст ответа модели.

        Raises:
            RuntimeError: Ошибка при обращении к Gemini API.
        """
        try:
            response: types.GenerateContentResponse = self._client.models.generate_content(
                model="gemini-2.5-flash-lite",
                contents=prompt,
                config=self._config,
            )
            return response.text
        except Exception as exc:
            logger.error("Ошибка вызова Gemini API: %s", exc)
            raise RuntimeError(f"Ошибка вызова Gemini API: {exc}") from exc


class GeminiAnalysisService:
    """Анализирует эмиссионную документацию облигаций через Google Gemini.

    Оркеструет получение Markdown-содержимого через репозиторий,
    формирование промта и валидацию ответа Gemini через Pydantic DTO.
    """

    def __init__(
        self,
        gemini_client: GeminiClientProtocol,
        markdown_repository: MarkdownRepositoryProtocol,
    ) -> None:
        """Инициализирует сервис с зависимостями.

        Args:
            gemini_client: Клиент для обращения к Gemini API.
            markdown_repository: Репозиторий для чтения Markdown-файлов.
        """
        self._client: GeminiClientProtocol = gemini_client
        self._markdown_repo: MarkdownRepositoryProtocol = markdown_repository

    def analyze(self, edisclosure_data: Dict[str, Any]) -> Optional[GeminiBondAnalysisDTO]:
        """Анализирует данные e-disclosure и возвращает структурированный результат.

        1. Извлекает события и имена Markdown-файлов из входного словаря.
        2. Читает содержимое Markdown-файлов через репозиторий.
        3. Формирует промт и отправляет в Gemini через клиент.
        4. Парсит JSON из ответа, валидирует через Pydantic.
        5. При ошибке валидации возвращает None — без исключения.
        6. Выводит результат в консоль.

        Args:
            edisclosure_data: Результат EdisclosureService.get_accrued_income_by_secid().
                Ожидаемые ключи: events, md_filenames.

        Returns:
            Валидированный GeminiBondAnalysisDTO или None при ошибке валидации/парсинга.
        """
        events: List[Dict[str, Any]] = edisclosure_data.get("events", [])
        md_filenames: List[str] = edisclosure_data.get("md_filenames", [])

        logger.info(
            "[GEMINI] Подготовка запроса: событий=%d, md-файлов=%d → %s",
            len(events),
            len(md_filenames),
            md_filenames,
        )

        markdown_content: str = self._markdown_repo.read_files(md_filenames)
        events_json: str = json.dumps(events, ensure_ascii=False, indent=2)

        prompt: str = _PROMPT_TEMPLATE.format(
            events_json=events_json,
            markdown_content=markdown_content,
        )

        logger.info(
            "[GEMINI] → POST https://generativelanguage.googleapis.com/ "
            "(model: gemini-2.5-flash-lite, длина промта: %d символов)",
            len(prompt),
        )

        try:
            raw_text: str = self._client.generate(prompt)
        except RuntimeError as exc:
            logger.error("[GEMINI] Ошибка вызова API: %s", exc)
            return None

        logger.info("[GEMINI] Ответ получен: %d символов", len(raw_text))

        try:
            parsed: Dict[str, Any] = _parse_json_response(raw_text)
        except ValueError as exc:
            logger.error("[GEMINI] Ошибка парсинга JSON из ответа: %s", exc)
            logger.debug("[GEMINI] Сырой ответ:\n%s", raw_text)
            return None

        try:
            result: GeminiBondAnalysisDTO = GeminiBondAnalysisDTO(**parsed)
        except ValidationError as exc:
            logger.error(
                "[GEMINI] Ответ не прошёл валидацию Pydantic (%d ошибок):\n%s",
                exc.error_count(),
                exc,
            )
            logger.debug("[GEMINI] Разобранный JSON:\n%s", json.dumps(parsed, ensure_ascii=False, indent=2))
            return None

        logger.info("[GEMINI] Валидация успешна")
        print(result.model_dump_json(indent=2))
        return result


def _parse_json_response(raw_text: str) -> Dict[str, Any]:
    """Извлекает JSON из текстового ответа Gemini.

    Удаляет маркдаун-обёртку ```json ... ``` если присутствует.

    Args:
        raw_text: Сырой текст ответа модели.

    Returns:
        Разобранный словарь.

    Raises:
        ValueError: Текст не содержит валидный JSON.
    """
    cleaned: str = re.sub(
        r"^\s*```(?:json)?\s*\n?", "", raw_text, flags=re.MULTILINE,
    )
    cleaned = re.sub(
        r"\n?\s*```\s*$", "", cleaned, flags=re.MULTILINE,
    )
    cleaned = cleaned.strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as exc:
        logger.error("Невалидный JSON в ответе Gemini: %s", exc)
        raise ValueError(
            f"Ответ Gemini не содержит валидный JSON: {exc}"
        ) from exc


_gemini_analysis_service: Optional[GeminiAnalysisService] = None


def get_gemini_analysis_service() -> GeminiAnalysisService:
    """Возвращает singleton GeminiAnalysisService.

    Raises:
        ValueError: GEMINI_API_KEY не задан в настройках.
    """
    global _gemini_analysis_service
    if _gemini_analysis_service is None:
        api_key: str = settings.GEMINI_API_KEY
        if not api_key:
            raise ValueError(
                "GEMINI_API_KEY не задан. Укажите ключ в .env файле."
            )
        _gemini_analysis_service = GeminiAnalysisService(
            gemini_client=GeminiClient(api_key=api_key),
            markdown_repository=MarkdownFileRepository(base_dir=_DATA_DIR),
        )
    return _gemini_analysis_service
