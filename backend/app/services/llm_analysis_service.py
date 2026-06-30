from pathlib import Path
from typing import Any, Dict, List, Optional, Set

import logging
from config.settings import settings
from app.core.exceptions import PromptTooLongError
from app.services.llm import providers
from app.services.llm.factory import LlmProviderFactory
from datetime import datetime
from app.services.llm.tasks.base import BaseAnalysisTask
from app.services.llm.tasks.floater_task import FloaterAnalysisTask
from app.services.llm.tasks.qa_task import QuestionAnsweringTask
from app.repository.db import get_history_repository
from app.services.llm.tasks.expand_query_task import ExpandQueryTask
from app.repository.files import get_markdownfile_repository
from app.repository.db import get_bonds_repository, get_bond_float_repository
from app.core.exceptions import GeminiUnavailableError, GeminiQuotaExhaustedError
from app.utils.rating_utils import standardize_rating
from app.services.llm_provider_resolution_service import get_llm_provider_resolution_service

from config.filters import FILENAME_EXCLUDE_PHRASES, HEADER_CONDITIONS, FLOAT_PARAMS_QUERIES

logger: logging.Logger = logging.getLogger(__name__)

_DATA_DIR: Path = Path(__file__).resolve().parent.parent / "data"


def _get_pipeline_logger() -> logging.Logger:
    """Returns a logger that writes to a separate log file for the LLM pipeline."""
    from config.paths import BACKEND_DIR

    log_dir: Path = BACKEND_DIR / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    logger_name: str = "llm_prompt_pipeline"
    pl_logger: logging.Logger = logging.getLogger(logger_name)
    if pl_logger.handlers:
        return pl_logger

    pl_logger.setLevel(logging.INFO)
    log_file: Path = log_dir / f"llm_prompt_pipeline_{datetime.now().strftime('%Y-%m-%d')}.log"
    fh: logging.FileHandler = logging.FileHandler(log_file, encoding="utf-8")
    fh.setLevel(logging.INFO)
    fmt: logging.Formatter = logging.Formatter(
        "%(asctime)s - %(levelname)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    )
    fh.setFormatter(fmt)
    pl_logger.addHandler(fh)
    pl_logger.propagate = False
    return pl_logger


class LLMAnalysisService:
    """Сервис-аналитик

    Координирует процесс формирования контекста из e-disclosure данных и файлов,
    выполняет запросы к LLM и обеспечивает строгую валидацию структурированных ответов.
    """

    def __init__(
            self,
    ) -> None:
        """Инициализирует сервис с зависимостями.

        Args:
            llm_provider: Клиент для обращения к LLM API.
            markdown_repository: Репозиторий для чтения Markdown-файлов.
            :rtype: None
        """
        from app.processors import get_bond_llm_processor

        self._markdown_repo = get_markdownfile_repository()
        self._bond_repository = get_bonds_repository()
        self._bond_float_repository = get_bond_float_repository()
        self._llm_provider_resolution_service = get_llm_provider_resolution_service()
        self._bond_llm_processor = get_bond_llm_processor()
        self._history_repo = get_history_repository()

    def _execute_task(
            self,
            llm_provider,
            data: Dict[str, Any],
            task: BaseAnalysisTask,
    ) -> Any:

        prompt: str = task.build_prompt(data)

        print(f"Промт для модели: {prompt}", flush=True)

        if len(prompt) > settings.FLOATER_ANALYSIS_PROMPT_MAX_CHARS:
            raise PromptTooLongError(
                message="Промт превышает лимит символов",
                length=len(prompt),
                limit=settings.FLOATER_ANALYSIS_PROMPT_MAX_CHARS
            )

        task_name: str = task.__class__.__name__
        logger.info("[LLM] → POST [%s] (Model: %s, Length: %d)", task_name, llm_provider, len(prompt))

        raw_text: str = llm_provider.generate(prompt)

        if not raw_text:
            logger.error("[LLM] [%s] Провайдер вернул пустой ответ.", task_name)
            return None

        logger.info("[LLM] [%s] Ответ получен: %d символов", task_name, len(raw_text))

        try:
            return task.parse_response_and_validate(raw_text, **data)
        except ValueError as exc:
            logger.error("[LLM] [%s] Ошибка парсинга/валидации в стратегии: %s", task_name, exc)
            return None

    def analysis_floaters_params(
            self,
            **params: Any
    ) -> Dict[str, Any]:
        """Анализирует параметры флоатера с использованием паттерна Стратегия."""

        pl_logger: logging.Logger = _get_pipeline_logger()
        task = FloaterAnalysisTask()
        # 1. Получаем конфигурацию и создаем объект провайдера через фабрику
        provider = params.get("provider")
        secid = params.get("secid")
        limit = params.get("limit")
        rating = standardize_rating(params.get("rating"))
        is_forced_update = params.get("is_forced_update")

        resolved_provider: str = self._llm_provider_resolution_service.resolve_provider(provider)

        cfg = settings.llm.providers[resolved_provider]
        llm_provider = LlmProviderFactory.create(cfg)

        if secid:  # Обработка для конкретной облигации по переданному secid
            total_all = 1
            to_process = [secid]
            already_done = 0
            no_documents = 0
            is_forced_update = True
        else:  # Пакетная обработка облигаций
            all_secids = self._bond_repository.get_floater_secids(rating=rating)
            total_all = len(all_secids)
            # Filter: only bonds are not yet in bond_float_params.
            existing_bond_ids: Set[int] = self._bond_float_repository.get_existing_bond_ids()
            to_process = []
            already_done = 0
            no_documents = 0

            for s in all_secids:
                bond_id: Optional[int] = self._bond_repository.get_bond_id_by_secid(s)
                if bond_id is not None and bond_id in existing_bond_ids:
                    already_done += 1
                    continue
                to_process.append(s)

        if limit is not None:
            to_process = to_process[:limit]

        total: int = len(to_process)
        processed: int = 0
        saved: int = 0
        not_found_secids: List[str] = []
        quota_exhausted_error: Optional[GeminiQuotaExhaustedError] = None
        for idx, s in enumerate(to_process, start=1):
            processed += 1
            try:
                data: Dict[str, Any] = self._bond_llm_processor.process_single_bond(
                    s,
                    pl_logger,
                    use_local_events=params.get("use_local_events"),
                    is_forced=is_forced_update,
                    embedding_model=params.get("embedding_model"),
                    queries=FLOAT_PARAMS_QUERIES,
                    filename_exclude_phrases=FILENAME_EXCLUDE_PHRASES,
                    header_conditions=HEADER_CONDITIONS
                )
                if data:
                    saved += 1
                    result = self._execute_task(llm_provider, data, task)
                    self._bond_float_repository.upsert(data["bond_id"], result)
                    print(f"[LLM] {idx}/{total} — {s}: saved", flush=True)
                else:
                    not_found_secids.append(s)
                    print(f"[LLM] {idx}/{total} — {s}: not found", flush=True)
            except GeminiQuotaExhaustedError as exc:
                quota_exhausted_error = exc
                pl_logger.error(
                    "[QUOTA EXHAUSTED] secid=%s: %s", s, exc, exc_info=True,
                )
                print(
                    "[LLM] Pipeline stopped: Gemini API quota exhausted (429).",
                    flush=True,
                )
                break
            except GeminiUnavailableError as exc:
                pl_logger.error(
                    "[UNAVAILABLE] secid=%s: %s", s, exc, exc_info=True,
                )
                print(
                    "[LLM] Pipeline stopped: LLM API 503 UNAVAILABLE.",
                    flush=True,
                )
                raise
            except Exception as exc:
                pl_logger.error(
                    "[ERROR] secid=%s: %s", s, exc, exc_info=True,
                )
                not_found_secids.append(s)
                print(f"[LLM] {idx}/{total} — {s}: error ({exc})", flush=True)

        summary: str = (
            f"[LLM PIPELINE DONE] Processed: {processed}, "
            f"saved: {saved}, not found: {len(not_found_secids)}"
        )
        pl_logger.info(summary)
        pl_logger.info("=" * 60)
        print(summary, flush=True)

        if quota_exhausted_error is not None:
            raise quota_exhausted_error

        return {
            "status": "ok",
            "total_floaters": total_all,
            "already_analyzed": already_done,
            "no_documents": no_documents,
            "processed": processed,
            "saved": saved,
            "not_found": len(not_found_secids),
            "not_found_secids": not_found_secids,
        }

    def answer_question(
            self,
            **params: Any
    ) -> Dict[str, Any]:
        """Отвечает на вопрос по контексту документов с использованием паттерна Стратегия."""

        pl_logger: logging.Logger = _get_pipeline_logger()

        # 1. Получаем конфигурацию и создаем объект провайдера через фабрику
        provider = params.get("provider")
        secid = params.get("secid")
        regnumber = params.get("regnumber")

        inn: Optional[str] = self._bond_repository.get_emitent_inn_by_secid(secid)
        if not inn:
            pl_logger.warning(f"[SKIP] secid={secid}: ИНН эмитента не найден в базе")
            return {}

        resolved_provider: str = self._llm_provider_resolution_service.resolve_provider(provider)

        cfg = settings.llm.providers[resolved_provider]
        llm_provider = LlmProviderFactory.create(cfg)
        query = params.get("query")

        """Расширяет поисковый запрос пользователя с использованием паттерна Стратегия."""

        first_tradedate = self._history_repo.get_first_tradedate(secid)
        date_str: str = (
            first_tradedate.isoformat() if first_tradedate is not None else "2000-01-01"
        )
        print(f"Впорос пользователя: {query}. Дата начала торгов: {date_str}", flush=True)
        task = ExpandQueryTask(query)

        expand_query_result = self._execute_task(llm_provider, {"first_date_trade": date_str}, task)

        print(f"Обогащенный запрос: {expand_query_result}", flush=True)

        data: Dict[str, Any] = self._bond_llm_processor.process_single_bond(
            secid,
            pl_logger,
            use_local_events=params.get("use_local_events"),
            embedding_model=params.get("embedding_model"),
            queries=expand_query_result,
            filename_exclude_phrases=("Сертификат", "vector_context"),
            start_date=expand_query_result["start_date"]
        )

        data["queries"] = query

        task = QuestionAnsweringTask()
        result = self._execute_task(llm_provider, data, task)

        return {
            "query": params.get("query"),
            "answer": result
        }

_llm_analysis_service: Optional[LLMAnalysisService] = None


def init_llm_analysis_service() -> None:
    global _llm_analysis_service
    _llm_analysis_service = LLMAnalysisService()


def get_llm_analysis_service() -> LLMAnalysisService:
    if _llm_analysis_service is None:
        raise RuntimeError("LLMAnalysisService not initialized. Call init_llm_analysis_service first.")
    return _llm_analysis_service
