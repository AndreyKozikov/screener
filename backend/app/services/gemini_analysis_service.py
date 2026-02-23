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
from app.models.schemasDTO.gemini_dto import GeminiBondAnalysisDTO
from app.repository.files.markdown_repository import MarkdownFileRepository
from app.utils.llm_response_validation import validate_analysis_response
from config.llm_prompts import build_floater_analysis_prompt
from config.settings import settings

logger: logging.Logger = logging.getLogger(__name__)

_DATA_DIR: Path = Path(__file__).resolve().parent.parent / "data"

# Маркеры в тексте ошибки API при исчерпании квоты (429).
_GEMINI_QUOTA_EXHAUSTED_MARKERS: tuple[str, ...] = ("429", "RESOURCE_EXHAUSTED", "quota")

# Маркеры в тексте ошибки API при временной недоступности (503).
_GEMINI_UNAVAILABLE_MARKERS: tuple[str, ...] = ("503", "UNAVAILABLE")

# Идентификаторы моделей Google Gemini API.
GEMINI_MODEL_FLASH_LITE: str = "gemini-2.5-flash-lite"
GEMINI_MODEL_FLASH: str = "gemini-2.5-flash"
GEMINI_MODEL_3_FLASH: str = "gemini-3-flash-preview"


class GeminiQuotaExhaustedError(RuntimeError):
    """Исключение при исчерпании квоты Gemini API (429 RESOURCE_EXHAUSTED).

    При получении этой ошибки пайплайн анализа эмиссионных документов должен
    быть остановлен и процесс полностью завершён.
    """

    pass


class GeminiUnavailableError(RuntimeError):
    """Исключение при временной недоступности Gemini API (503 UNAVAILABLE).

    Требует повторной попытки с паузой; при многократной ошибке пайплайн
    должен быть остановлен.
    """

    pass


class GeminiClientProtocol(Protocol):
    """Протокол транспортного клиента для Gemini API."""

    def generate(self, prompt: str, model: Optional[str] = None) -> str:
        """Отправляет промт в указанную модель и возвращает текст ответа."""
        ...


class MarkdownRepositoryProtocol(Protocol):
    """Протокол репозитория для чтения Markdown-файлов."""

    def read_files(self, filenames: List[str]) -> str:
        """Читает и объединяет содержимое файлов."""
        ...

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

    def generate(self, prompt: str, model: Optional[str] = None) -> str:
        """Отправляет промт в Gemini и возвращает текст ответа.

        Args:
            prompt: Полный текст промта.
            model: Идентификатор модели (например gemini-2.5-flash-lite, gemini-2.5-flash).
                По умолчанию — gemini-2.5-flash-lite.

        Returns:
            Текст ответа модели.

        Raises:
            RuntimeError: Ошибка при обращении к Gemini API.
        """
        model_id: str = model or GEMINI_MODEL_FLASH_LITE
        try:
            response: types.GenerateContentResponse = self._client.models.generate_content(
                model=model_id,
                contents=prompt,
                config=self._config,
            )
            return response.text
        except Exception as exc:
            exc_str: str = str(exc)
            if all(m in exc_str for m in _GEMINI_QUOTA_EXHAUSTED_MARKERS):
                logger.error(
                    "[GEMINI] Исчерпана квота API (429 RESOURCE_EXHAUSTED). "
                    "Пайплайн должен быть остановлен: %s",
                    exc,
                )
                raise GeminiQuotaExhaustedError(
                    f"Исчерпана квота Gemini API (429 RESOURCE_EXHAUSTED). "
                    f"Остановите пайплайн и повторите позже. Детали: {exc}"
                ) from exc
            if all(m in exc_str for m in _GEMINI_UNAVAILABLE_MARKERS):
                logger.warning(
                    "[GEMINI] Временная недоступность API (503 UNAVAILABLE): %s",
                    exc,
                )
                raise GeminiUnavailableError(
                    f"Ошибка вызова Gemini API: 503 UNAVAILABLE. {exc}"
                ) from exc
            logger.error("Ошибка вызова Gemini API: %s", exc)
            raise RuntimeError(f"Ошибка вызова Gemini API: {exc}") from exc




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

    def analyze(
        self,
        edisclosure_data: Dict[str, Any],
        model: Optional[str] = None,
    ) -> Optional[GeminiBondAnalysisDTO]:
        """Анализирует данные e-disclosure и возвращает структурированный результат.

        1. Извлекает события и имена Markdown-файлов из входного словаря.
        2. Читает содержимое Markdown-файлов через репозиторий.
        3. Формирует промт и отправляет в Gemini через клиент (указанная модель).
        4. Парсит JSON из ответа, валидирует через Pydantic.
        5. При ошибке валидации возвращает None — без исключения.
        6. Выводит результат в консоль.

        Args:
            edisclosure_data: Результат EdisclosureService.get_accrued_income_by_secid().
                Ожидаемые ключи: events, md_filenames.
            model: Идентификатор модели Gemini (gemini-2.5-flash-lite, gemini-2.5-flash).
                По умолчанию — gemini-2.5-flash-lite.

        Returns:
            Валидированный GeminiBondAnalysisDTO или None при ошибке валидации/парсинга.
        """
        events: List[Dict[str, Aclass GeminiAnalysisService:
    """Анализирует эмиссионную документацию облигаций через Google Gemini.

    Оркеструет получение Markdown-содержимого через репозиторий,
    формирование промта и валидацию ответа Gemini через Pydantic DTO.
    """ny]] = edisclosure_data.get("events", [])
        md_filenames: List[str] = edisclosure_data.get("md_filenames", [])

        logger.info(
            "[GEMINI] Подготовка запроса: событий=%d, md-файлов=%d → %s",
            len(events),
            len(md_filenames),
            md_filenames,
        )

        md_base_dir: Optional[Path] = edisclosure_data.get("data_dir")
        if md_base_dir is not None and not isinstance(md_base_dir, Path):
            md_base_dir = Path(str(md_base_dir))
        markdown_content: str = self._markdown_repo.read_files(
            md_filenames, base_dir=md_base_dir
        )
        events_json: str = json.dumps(events, ensure_ascii=False, indent=2)

        prompt: str = build_floater_analysis_prompt(
            events_json=events_json,
            markdown_content=markdown_content,
        )

        model_id: str = model or GEMINI_MODEL_FLASH_LITE
        logger.info(
            "[GEMINI] → POST https://generativelanguage.googleapis.com/ "
            "(model: %s, длина промта: %d символов)",
            model_id, len(prompt),
        )
        print(
            f"  [API] POST https://generativelanguage.googleapis.com/ (Gemini API, model: {model_id})",
            flush=True,
        )

        try:
            raw_text: str = self._client.generate(prompt, model=model_id)
        except GeminiQuotaExhaustedError:
            raise
        except GeminiUnavailableError:
            raise
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

        print(
            "[GEMINI] Ответ модели до валидации Pydantic:\n"
            + json.dumps(parsed, ensure_ascii=False, indent=2),
            flush=True,
        )
        fallback_inn: Optional[str] = edisclosure_data.get("fallback_inn")
        result: Optional[GeminiBondAnalysisDTO] = validate_analysis_response(
            parsed, fallback_inn=fallback_inn
        )
        if result is None:
            logger.error("[GEMINI] Ответ не прошёл валидацию Pydantic (см. [LLM VALIDATION])")
            print("[GEMINI] Валидация не пройдена (подстановки применены, повторная валидация не удалась)", flush=True)
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
