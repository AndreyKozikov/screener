"""Сервис анализа облигационных данных через локальный HTTP API языковых моделей.

Обеспечивает взаимодействие с локально развернутыми моделями (например, Qwen или Llama)
для выполнения конфиденциального анализа документов без отправки данных во внешние облака.
"""

import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Protocol

import requests

from app.models.schemasDTO.llm_floatbond_dto import GeminiBondAnalysisDTO
from app.repository.files.markdown_repository import MarkdownFileRepository
from app.utils.llm_response_validation import validate_analysis_response
from app.core.exceptions import PromptTooLongError
from config.llm_prompts import build_floater_analysis_chatml_message
from config.settings import settings

logger: logging.Logger = logging.getLogger(__name__)

_DATA_DIR: Path = Path(__file__).resolve().parent.parent / "data"

class LocalLLMClientProtocol(Protocol):
    """Протокол транспортного клиента для локального LLM API."""

    @property
    def request_url(self) -> str:
        """Полный URL endpoint для генерации."""
        ...

    def generate(self, prompt: str) -> str:
        """Отправляет промт и возвращает текст ответа."""
        ...


class MarkdownRepositoryProtocol(Protocol):
    """Протокол репозитория для чтения Markdown-файлов."""

    def read_files(
        self, filenames: List[str], base_dir: Optional[Path] = None
    ) -> str:
        """Читает и объединяет содержимое файлов."""
        ...


class LocalLLMClient:
    """HTTP-клиент для взаимодействия с локальным сервером вывода LLM.

    Реализует специфичный для проекта протокол обмена данными с внутренним
    сервисом генерации текста.
    """

    def __init__(self, base_url: str, generate_path: str) -> None:
        """Инициализирует клиент.

        Args:
            base_url: Базовый URL сервиса (например, http://localhost:5000).
            generate_path: Путь endpoint генерации (например, /api/v1/llm/generate).
        """
        self._base_url: str = base_url.rstrip("/")
        self._generate_url: str = f"{self._base_url}{generate_path}"
        self._timeout: Optional[float] = None

    @property
    def request_url(self) -> str:
        """Возвращает полный URL endpoint генерации."""
        return self._generate_url

    def generate(self, prompt: str) -> str:
        """Отправляет промт в локальный сервис и возвращает текст ответа.

        Args:
            prompt: Полный текст промта.

        Returns:
            Текст ответа модели (поле response из JSON).

        Raises:
            RuntimeError: Ошибка при обращении к API или пустой ответ.
        """
        try:
            payload: Dict[str, Any] = {
                "message": prompt,
                "max_new_tokens": settings.LOCAL_LLM_ANALYSIS_MAX_NEW_TOKENS,
                "temperature": settings.LOCAL_LLM_ANALYSIS_TEMPERATURE,
                "top_p": settings.LOCAL_LLM_ANALYSIS_TOP_P,
            }
            resp = requests.post(self._generate_url, json=payload, timeout=self._timeout)
            resp.raise_for_status()
            response_payload: Dict[str, Any] = resp.json()
            content: Optional[str] = response_payload.get("response")
            if content is None:
                raise RuntimeError("Локальный LLM API вернул ответ без поля 'response'")
            return content
        except requests.RequestException as exc:
            logger.error("Ошибка вызова локального LLM API: %s", exc)
            raise RuntimeError(f"Ошибка вызова локального LLM API: {exc}") from exc
        except RuntimeError:
            raise
        except Exception as exc:
            logger.error("Ошибка вызова локального LLM API: %s", exc)
            raise RuntimeError(f"Ошибка вызова локального LLM API: {exc}") from exc


class LocalLLMAnalysisService:
    """Сервис-аналитик на базе локальных моделей.

    Выполняет полный цикл подготовки контекста и извлечения данных из документов,
    используя мощности локального GPU/CPU для обработки конфиденциальной информации.
    """

    def __init__(
        self,
        local_client: LocalLLMClientProtocol,
        markdown_repository: MarkdownRepositoryProtocol,
    ) -> None:
        self._client: LocalLLMClientProtocol = local_client
        self._markdown_repo: MarkdownRepositoryProtocol = markdown_repository

    def analyze(self, edisclosure_data: Dict[str, Any]) -> Optional[GeminiBondAnalysisDTO]:
        """Анализирует данные e-disclosure и возвращает структурированный результат."""
        events: List[Dict[str, Any]] = edisclosure_data.get("events", [])
        md_filenames: List[str] = edisclosure_data.get("md_filenames", [])
        vector_context: str = str(edisclosure_data.get("vector_context") or "").strip()

        logger.info(
            "[LOCAL LLM] Подготовка запроса: событий=%d, md-файлов=%d, vector_context=%d chars → %s",
            len(events),
            len(md_filenames),
            len(vector_context),
            md_filenames,
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

        prompt: str = build_floater_analysis_chatml_message(
            events_json=events_json,
            markdown_content=markdown_content,
        )

        prompt_len = len(prompt)
        if prompt_len > settings.FLOATER_ANALYSIS_PROMPT_MAX_CHARS:
            logger.warning(
                "[LOCAL LLM] Промпт слишком длинный (%d символов > %d), анализ отменён",
                prompt_len, settings.FLOATER_ANALYSIS_PROMPT_MAX_CHARS
            )
            raise PromptTooLongError(
                f"Промпт слишком длинный ({prompt_len} символов)",
                length=prompt_len,
                limit=settings.FLOATER_ANALYSIS_PROMPT_MAX_CHARS
            )

        logger.info(
            "[LOCAL LLM] → POST %s (длина промта: %d символов)",
            self._client.request_url,
            len(prompt),
        )

        try:
            raw_text: str = self._client.generate(prompt)
        except RuntimeError as exc:
            logger.error("[LOCAL LLM] Ошибка вызова API: %s", exc)
            return None

        logger.info("[LOCAL LLM] Ответ получен: %d символов", len(raw_text))

        try:
            parsed: Dict[str, Any] = _parse_json_response(raw_text)
        except ValueError as exc:
            logger.error("[LOCAL LLM] Ошибка парсинга JSON из ответа: %s", exc)
            logger.debug("[LOCAL LLM] Сырой ответ:\n%s", raw_text)
            return None

        print(
            "[LOCAL LLM] Ответ модели до валидации Pydantic:\n"
            + json.dumps(parsed, ensure_ascii=False, indent=2),
            flush=True,
        )
        fallback_inn: Optional[str] = edisclosure_data.get("fallback_inn")
        result: Optional[GeminiBondAnalysisDTO] = validate_analysis_response(
            parsed, fallback_inn=fallback_inn
        )
        if result is None:
            logger.error("[LOCAL LLM] Ответ не прошёл валидацию Pydantic (см. [LLM VALIDATION])")
            return None
        logger.info("[LOCAL LLM] Валидация успешна")
        print(result.model_dump_json(indent=2))
        return result


def _parse_json_response(raw_text: str) -> Dict[str, Any]:
    """Извлекает JSON из текста (удаляет обёртку ```json ... ```)."""
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
        logger.error("Невалидный JSON в ответе локального LLM: %s", exc)
        raise ValueError(
            f"Ответ локального LLM не содержит валидный JSON: {exc}"
        ) from exc


_local_analysis_service: Optional[LocalLLMAnalysisService] = None


def get_local_analysis_service() -> LocalLLMAnalysisService:
    """Возвращает singleton LocalLLMAnalysisService.

    Raises:
        ValueError: LOCAL_LLM_BASE_URL пустой (если проверка включена).
    """
    global _local_analysis_service
    if _local_analysis_service is None:
        base_url: str = settings.LOCAL_LLM_BASE_URL
        generate_path: str = settings.LOCAL_LLM_GENERATE_PATH
        _local_analysis_service = LocalLLMAnalysisService(
            local_client=LocalLLMClient(
                base_url=base_url,
                generate_path=generate_path,
            ),
            markdown_repository=MarkdownFileRepository(base_dir=_DATA_DIR),
        )
    return _local_analysis_service
