"""Сервис анализа облигационных данных через локальный LLM (Qwen3-4B по API из Docs/API_GUIDE.md).

POST /ask с multipart/form-data: prompt, опционально files.
Тот же структурированный JSON-анализ, что в gemini_analysis_service.py.
Возвращает GeminiBondAnalysisDTO.
"""

import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Protocol

import requests

from app.models.schemasDTO.gemini_dto import GeminiBondAnalysisDTO
from app.repository.files.markdown_repository import MarkdownFileRepository
from app.utils.llm_response_validation import validate_analysis_response
from config.llm_prompts import build_floater_analysis_prompt
from config.settings import settings

logger: logging.Logger = logging.getLogger(__name__)

_DATA_DIR: Path = Path(__file__).resolve().parent.parent / "data"

_DEFAULT_LOCAL_LLM_BASE_URL: str = "http://localhost:5000"
_LOCAL_ASK_PATH: str = "/ask"
_REQUEST_TIMEOUT: int = 300


class LocalLLMClientProtocol(Protocol):
    """Протокол транспортного клиента для локального LLM API."""

    def generate(self, prompt: str) -> str:
        """Отправляет промт и возвращает текст ответа."""
        ...


class MarkdownRepositoryProtocol(Protocol):
    """Протокол репозитория для чтения Markdown-файлов."""

    def read_files(self, filenames: List[str]) -> str:
        """Читает и объединяет содержимое файлов."""
        ...


class LocalLLMClient:
    """Клиент для локального LLM API (POST /ask по Docs/API_GUIDE.md)."""

    def __init__(self, base_url: str) -> None:
        """Инициализирует клиент.

        Args:
            base_url: Базовый URL сервиса (например, http://localhost:5000).
        """
        self._base_url: str = base_url.rstrip("/")
        self._ask_url: str = f"{self._base_url}{_LOCAL_ASK_PATH}"
        self._timeout: int = _REQUEST_TIMEOUT

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
            resp = requests.post(
                self._ask_url,
                data={"prompt": prompt},
                timeout=self._timeout,
            )
            resp.raise_for_status()
            payload: Dict[str, Any] = resp.json()
            content: Optional[str] = payload.get("response")
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
    """Анализирует эмиссионную документацию через локальную модель (Qwen3-4B).

    Тот же алгоритм, что у Gemini/OpenRouter: промпт + парсинг JSON + DTO.
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

        logger.info(
            "[LOCAL LLM] Подготовка запроса: событий=%d, md-файлов=%d → %s",
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
        print("  [LLM] Модель получает данные: в виде контекста в промте", flush=True)
        events_json: str = json.dumps(events, ensure_ascii=False, indent=2)

        prompt: str = build_floater_analysis_prompt(
            events_json=events_json,
            markdown_content=markdown_content,
        )

        logger.info(
            "[LOCAL LLM] → POST %s (длина промта: %d символов)",
            _DEFAULT_LOCAL_LLM_BASE_URL + _LOCAL_ASK_PATH,
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
        base_url: str = getattr(
            settings, "LOCAL_LLM_BASE_URL", _DEFAULT_LOCAL_LLM_BASE_URL
        ) or _DEFAULT_LOCAL_LLM_BASE_URL
        _local_analysis_service = LocalLLMAnalysisService(
            local_client=LocalLLMClient(base_url=base_url),
            markdown_repository=MarkdownFileRepository(base_dir=_DATA_DIR),
        )
    return _local_analysis_service
