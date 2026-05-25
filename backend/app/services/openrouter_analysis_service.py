"""Сервис анализа облигационных данных через агрегатор OpenRouter API.

Модуль обеспечивает доступ к широкому спектру языковых моделей (преимущественно
DeepSeek v4 Pro) через единый унифицированный интерфейс OpenRouter.
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
from config.llm_prompts import build_floater_analysis_prompt
from config.settings import settings

logger: logging.Logger = logging.getLogger(__name__)

_DATA_DIR: Path = Path(__file__).resolve().parent.parent / "data"

OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"
OPENROUTER_MODEL: str = "deepseek/deepseek-v4-pro"


class OpenRouterClientProtocol(Protocol):
    """Протокол транспортного клиента для OpenRouter API."""

    def generate(self, prompt: str) -> str:
        """Отправляет промт и возвращает текст ответа."""
        ...


class MarkdownRepositoryProtocol(Protocol):
    """Протокол репозитория для чтения Markdown-файлов."""

    def read_files(self, filenames: List[str]) -> str:
        """Читает и объединяет содержимое файлов."""
        ...


def _build_openrouter_headers() -> Dict[str, str]:
    """Формирует опциональные заголовки для OpenRouter (HTTP-Referer, X-Title)."""
    headers: Dict[str, str] = {}
    if getattr(settings, "OPENROUTER_HTTP_REFERER", None) and settings.OPENROUTER_HTTP_REFERER:
        headers["HTTP-Referer"] = settings.OPENROUTER_HTTP_REFERER
    if getattr(settings, "OPENROUTER_X_TITLE", None) and settings.OPENROUTER_X_TITLE:
        headers["X-Title"] = settings.OPENROUTER_X_TITLE
    return headers


class OpenRouterClient:
    """Транспортный клиент для OpenRouter.

    Реализует OpenAI-совместимый протокол для взаимодействия с агрегатором моделей,
    поддерживая специфичные заголовки и маршрутизацию.
    """

    def __init__(self, api_key: str) -> None:
        """Инициализирует OpenAI-клиент для OpenRouter.

        Args:
            api_key: OPENROUTER_API_KEY из настроек.
        """
        default_headers: Dict[str, str] = _build_openrouter_headers()
        self._client: OpenAI = OpenAI(
            base_url=OPENROUTER_BASE_URL,
            api_key=api_key,
            default_headers=default_headers if default_headers else None,
        )
        self._model: str = OPENROUTER_MODEL
        self._temperature: float = 0.1

    def generate(self, prompt: str) -> str:
        """Отправляет промт в OpenRouter и возвращает текст ответа.

        Args:
            prompt: Полный текст промта.

        Returns:
            Текст ответа модели.

        Raises:
            RuntimeError: Ошибка при обращении к OpenRouter API.
        """
        try:
            # Для DeepSeek v4 Pro добавляем поддержку reasoning режима
            extra_body = {}
            if "deepseek-v4-pro" in self._model:
                extra_body["reasoning"] = {"enabled": True}
            
            completion = self._client.chat.completions.create(
                model=self._model,
                messages=[{"role": "user", "content": prompt}],
                temperature=self._temperature,
                extra_body=extra_body if extra_body else None,
            )
            content: Optional[str] = (
                completion.choices[0].message.content if completion.choices else None
            )
            if content is None:
                raise RuntimeError("OpenRouter API вернул пустой ответ")
            return content
        except RuntimeError:
            raise
        except Exception as exc:
            logger.error("Ошибка вызова OpenRouter API: %s", exc)
            raise RuntimeError(f"Ошибка вызова OpenRouter API: {exc}") from exc


class OpenRouterAnalysisService:
    """Сервис-аналитик на базе OpenRouter.

    Координирует процесс анализа документов, позволяя гибко выбирать
    наиболее эффективную модель через API OpenRouter.
    """

    def __init__(
        self,
        openrouter_client: OpenRouterClientProtocol,
        markdown_repository: MarkdownRepositoryProtocol,
    ) -> None:
        self._client: OpenRouterClientProtocol = openrouter_client
        self._markdown_repo: MarkdownRepositoryProtocol = markdown_repository

    def analyze(self, edisclosure_data: Dict[str, Any]) -> Optional[GeminiBondAnalysisDTO]:
        """Анализирует данные e-disclosure и возвращает структурированный результат.

        Args:
            edisclosure_data: Результат с ключами events, md_filenames.

        Returns:
            Валидированный GeminiBondAnalysisDTO или None при ошибке валидации/парсинга.
        """
        events: List[Dict[str, Any]] = edisclosure_data.get("events", [])
        md_filenames: List[str] = edisclosure_data.get("md_filenames", [])
        vector_context: str = str(edisclosure_data.get("vector_context") or "").strip()

        logger.info(
            "[OPENROUTER] Подготовка запроса: событий=%d, md-файлов=%d, vector_context=%d chars → %s",
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

        prompt: str = build_floater_analysis_prompt(
            events_json=events_json,
            markdown_content=markdown_content,
        )

        prompt_len = len(prompt)
        if prompt_len > settings.FLOATER_ANALYSIS_PROMPT_MAX_CHARS:
            logger.warning(
                "[OPENROUTER] Промпт слишком длинный (%d символов > %d), анализ отменён",
                prompt_len, settings.FLOATER_ANALYSIS_PROMPT_MAX_CHARS
            )
            raise PromptTooLongError(
                f"Промпт слишком длинный ({prompt_len} символов)",
                length=prompt_len,
                limit=settings.FLOATER_ANALYSIS_PROMPT_MAX_CHARS
            )

        logger.info(
            "[OPENROUTER] → POST %s (model: %s, длина промта: %d символов)",
            OPENROUTER_BASE_URL,
            OPENROUTER_MODEL,
            len(prompt),
        )

        try:
            raw_text: str = self._client.generate(prompt)
        except RuntimeError as exc:
            logger.error("[OPENROUTER] Ошибка вызова API: %s", exc)
            return None

        logger.info("[OPENROUTER] Ответ получен: %d символов", len(raw_text))

        try:
            parsed: Dict[str, Any] = _parse_json_response(raw_text)
        except ValueError as exc:
            logger.error("[OPENROUTER] Ошибка парсинга JSON из ответа: %s", exc)
            logger.debug("[OPENROUTER] Сырой ответ:\n%s", raw_text)
            return None

        print(
            "[OPENROUTER] Ответ модели до валидации Pydantic:\n"
            + json.dumps(parsed, ensure_ascii=False, indent=2),
            flush=True,
        )
        fallback_inn: Optional[str] = edisclosure_data.get("fallback_inn")
        result: Optional[GeminiBondAnalysisDTO] = validate_analysis_response(
            parsed, fallback_inn=fallback_inn
        )
        if result is None:
            logger.error("[OPENROUTER] Ответ не прошёл валидацию Pydantic (см. [LLM VALIDATION])")
            print("[OPENROUTER] Валидация не пройдена", flush=True)
            return None
        logger.info("[OPENROUTER] Валидация успешна")
        print(result.model_dump_json(indent=2))
        return result


def _parse_json_response(raw_text: str) -> Dict[str, Any]:
    """Извлекает JSON из текстового ответа (удаляет обёртку ```json ... ```)."""
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
        logger.error("Невалидный JSON в ответе OpenRouter: %s", exc)
        raise ValueError(
            f"Ответ OpenRouter не содержит валидный JSON: {exc}"
        ) from exc


_openrouter_analysis_service: Optional[OpenRouterAnalysisService] = None


def get_openrouter_analysis_service() -> OpenRouterAnalysisService:
    """Возвращает singleton OpenRouterAnalysisService.

    Raises:
        ValueError: OPENROUTER_API_KEY не задан в настройках.
    """
    global _openrouter_analysis_service
    if _openrouter_analysis_service is None:
        api_key: str = settings.OPENROUTER_API_KEY
        if not api_key:
            raise ValueError(
                "OPENROUTER_API_KEY не задан. Укажите ключ в .env файле."
            )
        _openrouter_analysis_service = OpenRouterAnalysisService(
            openrouter_client=OpenRouterClient(api_key=api_key),
            markdown_repository=MarkdownFileRepository(base_dir=_DATA_DIR),
        )
    return _openrouter_analysis_service
