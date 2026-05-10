"""Сервис глубокого анализа эмиссионной документации через OpenAI API (GPT-5.1).

Модуль реализует интеллектуальную обработку накопленных документов и событий
для извлечения сложных параметров облигаций, обеспечивая единообразную обработку
ошибок и форматов данных с другими LLM-провайдерами.
"""

import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Protocol

from openai import OpenAI

from app.models.schemasDTO.gemini_dto import GeminiBondAnalysisDTO
from app.repository.files.markdown_repository import MarkdownFileRepository
from app.utils.llm_response_validation import validate_analysis_response
from app.core.exceptions import PromptTooLongError
from app.services.gemini_analysis_service import (
    GeminiQuotaExhaustedError,
    GeminiUnavailableError,
)
from config.llm_prompts import build_floater_analysis_prompt
from config.settings import settings

logger: logging.Logger = logging.getLogger(__name__)

_DATA_DIR: Path = Path(__file__).resolve().parent.parent / "data"

# Идентификатор модели OpenAI GPT-5.1.
OPENAI_MODEL_GPT_5_1: str = "gpt-5.1"

# Маркеры в тексте ошибки API при исчерпании квоты (429).
_OPENAI_QUOTA_EXHAUSTED_MARKERS: tuple[str, ...] = ("429", "rate_limit", "quota")

# Маркеры в тексте ошибки API при временной недоступности (503).
_OPENAI_UNAVAILABLE_MARKERS: tuple[str, ...] = ("503", "unavailable", "service")


class OpenAIClientProtocol(Protocol):
    """Протокол транспортного клиента для OpenAI API."""

    def generate(
        self,
        prompt: str,
        model: Optional[str] = None,
        file_paths: Optional[List[str]] = None,
        base_dir: Optional[Path] = None,
    ) -> str:
        """Отправляет промт в указанную модель и возвращает текст ответа.

        При наличии file_paths и base_dir загружает .md-файлы через Files API
        и передаёт их через Responses API вместе с промтом.
        """
        ...


class MarkdownRepositoryProtocol(Protocol):
    """Протокол репозитория для чтения Markdown-файлов."""

    def read_files(
        self,
        filenames: List[str],
        base_dir: Optional[Path] = None,
    ) -> str:
        """Читает и объединяет содержимое файлов."""
        ...


class OpenAIClient:
    """Транспортный клиент для OpenAI API.

    Обеспечивает взаимодействие с моделями семейства GPT, поддерживая как
    стандартный чат-интерфейс, так и специализированное API для работы с файлами.
    """

    def __init__(self, api_key: str) -> None:
        """Настраивает OpenAI SDK и создаёт клиент.

        Args:
            api_key: Ключ API OpenAI (OPENAI_API_KEY).
        """
        self._client: OpenAI = OpenAI(api_key=api_key)
        self._temperature: float = 0.1

    def generate(
        self,
        prompt: str,
        model: Optional[str] = None,
        file_paths: Optional[List[str]] = None,
        base_dir: Optional[Path] = None,
    ) -> str:
        """Отправляет промт в OpenAI и возвращает текст ответа.

        При наличии file_paths и base_dir загружает каждый .md-файл через
        OpenAI Files API (purpose="user_data") и вызывает Responses API,
        передавая файлы как input_file и промт как input_text.
        Иначе использует chat.completions.create с текстом промта.

        Args:
            prompt: Полный текст промта.
            model: Идентификатор модели (например gpt-5.1).
                По умолчанию — OPENAI_MODEL_GPT_5_1.
            file_paths: Список имён файлов (PDF, Word и др.) для загрузки через Files API.
                Требует base_dir. Если None или пуст — только текст промта.
            base_dir: Базовая директория, в которой расположены файлы из file_paths.

        Returns:
            Текст ответа модели.

        Raises:
            GeminiQuotaExhaustedError: При 429 / rate limit (квота исчерпана).
            GeminiUnavailableError: При 503 / временная недоступность.
            RuntimeError: Остальные ошибки вызова API.
        """
        model_id: str = model or OPENAI_MODEL_GPT_5_1
        try:
            if file_paths and base_dir is not None:
                uploaded_file_ids: List[str] = []
                for filename in file_paths:
                    file_path: Path = Path(base_dir) / filename
                    with open(file_path, "rb") as fh:
                        uploaded = self._client.files.create(file=fh, purpose="user_data")
                    uploaded_file_ids.append(uploaded.id)
                    logger.debug("[OPENAI] Files API: файл загружен %s → %s", file_path, uploaded.id)
                content_items: List[Dict[str, Any]] = [
                    {"type": "input_file", "file_id": fid} for fid in uploaded_file_ids
                ]
                content_items.append({"type": "input_text", "text": prompt})
                response = self._client.responses.create(
                    model=model_id,
                    input=[{"role": "user", "content": content_items}],
                )
                result_text: Optional[str] = response.output_text
                if result_text is None:
                    raise RuntimeError("OpenAI Responses API вернул пустой ответ")
                return result_text
            else:
                completion = self._client.chat.completions.create(
                    model=model_id,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=self._temperature,
                )
                content: Optional[str] = (
                    completion.choices[0].message.content if completion.choices else None
                )
                if content is None:
                    raise RuntimeError("OpenAI API вернул пустой ответ")
                return content
        except Exception as exc:
            exc_str: str = str(exc).lower()
            if any(m in exc_str for m in _OPENAI_QUOTA_EXHAUSTED_MARKERS):
                logger.error(
                    "[OPENAI] Исчерпана квота API (429). "
                    "Пайплайн должен быть остановлен: %s",
                    exc,
                )
                raise GeminiQuotaExhaustedError(
                    f"Исчерпана квота OpenAI API (429). "
                    f"Остановите пайплайн и повторите позже. Детали: {exc}"
                ) from exc
            if any(m in exc_str for m in _OPENAI_UNAVAILABLE_MARKERS):
                logger.warning(
                    "[OPENAI] Временная недоступность API (503): %s",
                    exc,
                )
                raise GeminiUnavailableError(
                    f"Ошибка вызова OpenAI API: 503 UNAVAILABLE. {exc}"
                ) from exc
            logger.error("Ошибка вызова OpenAI API: %s", exc)
            raise RuntimeError(f"Ошибка вызова OpenAI API: {exc}") from exc


class OpenAIAnalysisService:
    """Сервис-аналитик на базе OpenAI GPT.

    Оркестрирует процесс извлечения данных из документов e-disclosure,
    используя мощности моделей OpenAI для анализа сложных юридических текстов.
    """

    def __init__(
        self,
        openai_client: OpenAIClientProtocol,
        markdown_repository: MarkdownRepositoryProtocol,
    ) -> None:
        """Инициализирует сервис с зависимостями.

        Args:
            openai_client: Клиент для обращения к OpenAI API.
            markdown_repository: Репозиторий для чтения Markdown-файлов.
        """
        self._client: OpenAIClientProtocol = openai_client
        self._markdown_repo: MarkdownRepositoryProtocol = markdown_repository

    def analyze(
        self,
        edisclosure_data: Dict[str, Any],
        model: Optional[str] = None,
    ) -> Optional[GeminiBondAnalysisDTO]:
        """Анализирует данные e-disclosure и возвращает структурированный результат.

        1. Извлекает события и имена Markdown-файлов из входного словаря.
        2. Читает содержимое Markdown-файлов через репозиторий.
        3. Формирует промт и отправляет в OpenAI через клиент (указанная модель).
        4. Парсит JSON из ответа, валидирует через Pydantic (GeminiBondAnalysisDTO).
        5. При ошибке валидации возвращает None — без исключения.
        6. Выводит результат в консоль.

        Args:
            edisclosure_data: Результат EdisclosureService.get_accrued_income_by_secid().
                Ожидаемые ключи: events, md_filenames, data_dir (опционально).
            model: Идентификатор модели OpenAI (например gpt-5.1). По умолчанию — OPENAI_MODEL_GPT_5_1.

        Returns:
            Валидированный GeminiBondAnalysisDTO или None при ошибке валидации/парсинга.
        """
        events: List[Dict[str, Any]] = edisclosure_data.get("events", [])
        md_filenames: List[str] = edisclosure_data.get("md_filenames", [])
        doc_filenames: List[str] = edisclosure_data.get("doc_filenames", [])
        vector_context: str = str(edisclosure_data.get("vector_context") or "").strip()

        logger.info(
            "[OPENAI] Подготовка запроса: событий=%d, md-файлов=%d, doc-файлов=%d, vector_context=%d chars → %s",
            len(events),
            len(md_filenames),
            len(doc_filenames),
            len(vector_context),
            doc_filenames or md_filenames,
        )

        md_base_dir: Optional[Path] = edisclosure_data.get("data_dir")
        if md_base_dir is not None and not isinstance(md_base_dir, Path):
            md_base_dir = Path(str(md_base_dir))

        if vector_context:
            markdown_content: str = vector_context
            print("  [LLM] Модель получает данные: vector_context после векторного поиска", flush=True)
        else:
            markdown_content = self._markdown_repo.read_files(
                md_filenames, base_dir=md_base_dir
            )
            print("  [LLM] Модель получает данные: в виде контекста в промте", flush=True)

        events_json: str = json.dumps(events, ensure_ascii=False, indent=2)

        prompt: str = build_floater_analysis_prompt(
            events_json=events_json,
            markdown_content=markdown_content,
        )

        prompt_len = len(prompt)
        if prompt_len > settings.FLOATER_ANALYSIS_PROMPT_MAX_CHARS:
            logger.warning(
                "[OPENAI] Промпт слишком длинный (%d символов > %d), анализ отменён",
                prompt_len, settings.FLOATER_ANALYSIS_PROMPT_MAX_CHARS
            )
            raise PromptTooLongError(
                f"Промпт слишком длинный ({prompt_len} символов)",
                length=prompt_len,
                limit=settings.FLOATER_ANALYSIS_PROMPT_MAX_CHARS
            )

        model_id: str = model or OPENAI_MODEL_GPT_5_1
        logger.info(
            "[OPENAI] → POST https://api.openai.com/v1/ "
            "(model: %s, длина промта: %d символов)",
            model_id,
            len(prompt),
        )
        print(
            f"  [API] POST https://api.openai.com/v1/ (OpenAI, model: {model_id})",
            flush=True,
        )

        try:
            raw_text: str = self._client.generate(prompt, model=model_id)
        except GeminiQuotaExhaustedError:
            raise
        except GeminiUnavailableError:
            raise
        except RuntimeError as exc:
            logger.error("[OPENAI] Ошибка вызова API: %s", exc)
            return None

        logger.info("[OPENAI] Ответ получен: %d символов", len(raw_text))

        try:
            parsed: Dict[str, Any] = _parse_json_response(raw_text)
        except ValueError as exc:
            logger.error("[OPENAI] Ошибка парсинга JSON из ответа: %s", exc)
            logger.debug("[OPENAI] Сырой ответ:\n%s", raw_text)
            return None

        print(
            "[OPENAI] Ответ модели до валидации Pydantic:\n"
            + json.dumps(parsed, ensure_ascii=False, indent=2),
            flush=True,
        )
        fallback_inn: Optional[str] = edisclosure_data.get("fallback_inn")
        result: Optional[GeminiBondAnalysisDTO] = validate_analysis_response(
            parsed, fallback_inn=fallback_inn
        )
        if result is None:
            logger.error("[OPENAI] Ответ не прошёл валидацию Pydantic (см. [LLM VALIDATION])")
            print("[OPENAI] Валидация не пройдена", flush=True)
            return None
        logger.info("[OPENAI] Валидация успешна")
        print(result.model_dump_json(indent=2))
        return result


def _parse_json_response(raw_text: str) -> Dict[str, Any]:
    """Извлекает JSON из текстового ответа модели.

    Удаляет маркдаун-обёртку ```json ... ``` если присутствует.
    Логика идентична gemini_analysis_service._parse_json_response.

    Args:
        raw_text: Сырой текст ответа модели.

    Returns:
        Разобранный словарь.

    Raises:
        ValueError: Текст не содержит валидный JSON.
    """
    cleaned: str = re.sub(
        r"^\s*```(?:json)?\s*\n?",
        "",
        raw_text,
        flags=re.MULTILINE,
    )
    cleaned = re.sub(
        r"\n?\s*```\s*$",
        "",
        cleaned,
        flags=re.MULTILINE,
    )
    cleaned = cleaned.strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as exc:
        logger.error("Невалидный JSON в ответе OpenAI: %s", exc)
        raise ValueError(
            f"Ответ OpenAI не содержит валидный JSON: {exc}"
        ) from exc


_openai_analysis_service: Optional[OpenAIAnalysisService] = None


def get_openai_analysis_service() -> OpenAIAnalysisService:
    """Возвращает singleton OpenAIAnalysisService.

    Raises:
        ValueError: OPENAI_API_KEY не задан в настройках.
    """
    global _openai_analysis_service
    if _openai_analysis_service is None:
        api_key: str = settings.OPENAI_API_KEY
        if not api_key:
            raise ValueError(
                "OPENAI_API_KEY не задан. Укажите ключ в .env файле."
            )
        _openai_analysis_service = OpenAIAnalysisService(
            openai_client=OpenAIClient(api_key=api_key),
            markdown_repository=MarkdownFileRepository(base_dir=_DATA_DIR),
        )
    return _openai_analysis_service
