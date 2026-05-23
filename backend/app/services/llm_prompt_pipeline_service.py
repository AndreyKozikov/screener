"""Пайплайн №2 — Формирование промптов и анализ накопленных документов через LLM.

Данный сервис работает исключительно с локально сохраненными документами
(Markdown-файлы в backend/app/data/{secid}/). Он не выполняет скачивание,
а фокусируется на интеллектуальном анализе уже имеющихся данных.
"""

import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from app.core.exceptions import PromptTooLongError
from app.models.schemasDTO.gemini_dto import GeminiBondAnalysisDTO
from app.repository.db.bond_float_params_repository import BondFloatParamsRepository
from app.repository.files.file_storage import FileStorage
from app.services.bonds_service import (
    get_bond_id_by_secid,
    get_emitent_inn_by_secid,
    get_emitent_moex_id_by_secid,
    get_floater_secids,
    get_reg_number_by_secid,
)
from app.services.edisclosure_service import (
    EdisclosureService,
    SkipBondException,
    _get_not_found_float_params_data,
)
from app.services.gemini_analysis_service import (
    GeminiQuotaExhaustedError,
    GeminiUnavailableError,
)
from app.services.llm_provider_readiness_service import LlmProviderReadinessService
from app.services.trading_history_service import get_trading_history_service
from app.services.vector_retrieval.pipeline import RetrievalPipeline

from app.parsers.emission_series_parser import (
    extract_series_from_markdown,
    filter_events_by_secid_regnumber_series,
    markdown_has_decision_header,
)
from app.utils.edisclosure_utils import (
    clean_event_text,
    get_events_with_full_text_for_year,
)

logger: logging.Logger = logging.getLogger(__name__)

_DATA_DIR: Path = Path(__file__).resolve().parent.parent / "data"

_DEFAULT_DATE: str = "2025-04-24"

# Фразы в имени файла (без учёта регистра), при наличии которых файл не отправляется на конвертацию.
_FILENAME_EXCLUDE_PHRASES: tuple[str, ...] = (
    "Отчетность МСФО",
    "Отчетность РСБУ",
    "Отчетность",
    "МСФО",
    "РСБУ",
    "Проспект",
    "Сертификат",
    "vector_context",
)

_HEADER_CONDITIONS: str = "ДОКУМЕНТ, СОДЕРЖАЩИЙ УСЛОВИЯ РАЗМЕЩЕНИЯ ЦЕННЫХ БУМАГ"
_HEADER_DECISION: str = "РЕШЕНИЕ О ВЫПУСКЕ ЦЕННЫХ БУМАГ"
_HEADER_NOTICE_ISSUE: str = "Уведомление об итогах выпуска"


def _filename_excluded_from_pipeline(filename: str) -> bool:
    """True, если имя файла содержит одну из исключающих фраз (проверка без учёта регистра)."""
    if not filename or not isinstance(filename, str):
        return False
    name_lower: str = filename.lower()
    return any(phrase.lower() in name_lower for phrase in _FILENAME_EXCLUDE_PHRASES)


def _markdown_has_any_required_header(markdown: str) -> bool:
    """True, если в тексте есть хотя бы один из требуемых заголовков (без учёта регистра)."""
    if not markdown or not markdown.strip():
        return False
    md_lower: str = markdown.lower()
    return (
        _HEADER_CONDITIONS.lower() in md_lower
        or _HEADER_DECISION.lower() in md_lower
        or _HEADER_NOTICE_ISSUE.lower() in md_lower
    )


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


class LlmPromptPipelineService:
    """Сервис конвейерного анализа эмиссионной документации.

    Оркестрирует процесс отбора релевантных файлов, фильтрации событий раскрытия
    и генерации запросов к LLM для автоматизированного извлечения параметров
    облигаций-флоатеров.
    """

    def __init__(self) -> None:
        self._file_storage: FileStorage = FileStorage()
        self._float_params_repo: BondFloatParamsRepository = BondFloatParamsRepository()
        self._edisclosure_service: EdisclosureService = EdisclosureService()
        self._readiness: LlmProviderReadinessService = LlmProviderReadinessService()
        self._retrieval_pipeline: RetrievalPipeline = RetrievalPipeline()
        self._llm_call_timestamps: List[float] = []
        
        # New repo for event_details
        from app.repository.db.event_detail_repository import EventDetailRepository
        self._event_detail_repo: EventDetailRepository = EventDetailRepository()

    # ------------------------------------------------------------------
    # Public entry points
    # ------------------------------------------------------------------

    def run_llm_pipeline(
        self,
        provider: Optional[str] = None,
        limit: Optional[int] = None,
        rating: Optional[str] = None,
        use_file_upload: bool = False,
        use_local_events: bool = False,
        secid: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Run LLM analysis pipeline for floater bonds with already-downloaded documents.

        Args:
            provider: LLM provider name. None or empty — AUTO mode.
            limit: Maximum number of bonds to process. None — all with documents.
            rating: If set — only floaters with this credit rating.
            use_file_upload: If True — send original files via Files API.
            use_local_events: If True — load events from local JSON files.

        Returns:
            Summary dict with processing statistics.
        """
        resolved_provider: str = self._readiness.resolve_provider(provider)
        pl_logger: logging.Logger = _get_pipeline_logger()

        if secid:
            all_secids = [secid]
            total_all = 1
            to_process = [secid]
            already_done = 0
            no_documents = 0
            # Check if documents exist for the specific secid
            bond_dir: Path = _DATA_DIR / secid
            if not self._has_markdown_files(bond_dir):
                no_documents = 1
                to_process = []
        else:
            all_secids = get_floater_secids(rating=rating)
            total_all = len(all_secids)

            # Filter: only bonds that have downloaded documents (.md files) AND
            # are not yet in bond_float_params.
            existing_bond_ids: Set[int] = self._float_params_repo.get_existing_bond_ids()
            to_process = []
            already_done = 0
            no_documents = 0

            for s in all_secids:
                bond_id: Optional[int] = get_bond_id_by_secid(s)
                if bond_id is not None and bond_id in existing_bond_ids:
                    already_done += 1
                    continue
                bond_dir = _DATA_DIR / s
                if not self._has_markdown_files(bond_dir):
                    no_documents += 1
                    continue
                to_process.append(s)

        if limit is not None:
            to_process = to_process[:limit]

        total: int = len(to_process)
        pl_logger.info("=" * 60)
        pl_logger.info(
            "[LLM PIPELINE START] Total floaters: %d, already analyzed: %d, "
            "no documents: %d, to process: %d",
            total_all, already_done, no_documents, total,
        )
        print(
            f"[LLM PIPELINE] Total floaters: {total_all}, "
            f"already analyzed: {already_done}, "
            f"no documents: {no_documents}, to process: {total}",
            flush=True,
        )

        processed: int = 0
        saved: int = 0
        not_found_secids: List[str] = []
        quota_exhausted_error: Optional[GeminiQuotaExhaustedError] = None
        is_forced_update = secid is not None

        for idx, s in enumerate(to_process, start=1):
            processed += 1
            try:
                success: bool = self._process_single_bond(
                    s, pl_logger,
                    provider=resolved_provider,
                    use_file_upload=use_file_upload,
                    use_local_events=use_local_events,
                    is_forced=is_forced_update,
                )
                if success:
                    saved += 1
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
                    "[LLM] Pipeline stopped: Gemini API 503 UNAVAILABLE.",
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

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _has_markdown_files(bond_dir: Path) -> bool:
        """True if the bond directory exists and contains at least one .md file."""
        if not bond_dir.is_dir():
            return False
        return any(f.name.lower() != "vector_context.md" for f in bond_dir.glob("*.md"))

    def _process_single_bond(
        self,
        secid: str,
        pl_logger: logging.Logger,
        provider: str = "gemini",
        use_file_upload: bool = False,
        use_local_events: bool = False,
        is_forced: bool = False,
    ) -> bool:
        """Run the LLM analysis pipeline for a single bond.

        Steps:
        1. Read existing .md files from data/{secid}/.
        2. Apply existing filters (filename exclusion + header check).
        3. Extract series from Markdown (existing filter logic).
        4. Load events (locally or from server) and filter by secid/regnumber/series.
        5. Send prompt to LLM and save results.

        Returns:
            True if LLM analysis succeeded and was saved, False otherwise.
        """
        print(f"  [{secid}] LLM pipeline start", flush=True)
        bond_data_dir: Path = _DATA_DIR / secid
        if not bond_data_dir.is_dir():
            pl_logger.warning("[SKIP] secid=%s: data directory not found", secid)
            return False

        inn: Optional[str] = get_emitent_inn_by_secid(secid)
        if not inn:
            pl_logger.warning("[SKIP] secid=%s: emitent INN not found", secid)
            bond_id: Optional[int] = get_bond_id_by_secid(secid)
            if bond_id is not None and not is_forced:
                self._float_params_repo.upsert_not_found(
                    bond_id, _get_not_found_float_params_data()
                )
            return False

        regnumber: Optional[str] = get_reg_number_by_secid(secid)
        bond_id = get_bond_id_by_secid(secid)

        trading_service = get_trading_history_service()
        first_tradedate = trading_service.get_first_tradedate(secid)
        date_str: str = (
            first_tradedate.isoformat() if first_tradedate is not None else _DEFAULT_DATE
        )

        # --- Step 1: Collect existing document filenames from data dir ---
        doc_filenames: List[str] = self._list_document_files(bond_data_dir)
        print(
            f"  [{secid}] Found {len(doc_filenames)} document files in data dir",
            flush=True,
        )

        # --- Step 2: Apply existing filters (filename exclusion + header check) ---
        # This reuses the filter logic without re-downloading or re-converting.
        company_id: int
        companies: List[Dict[str, Any]]
        try:
            company_id, companies = self._edisclosure_service._resolve_company_id_by_inn(inn)
        except ValueError:
            pl_logger.warning(
                "[SKIP] secid=%s: company with INN=%s not found", secid, inn,
            )
            if bond_id is not None and not is_forced:
                self._float_params_repo.upsert_not_found(
                    bond_id, _get_not_found_float_params_data()
                )
            return False
        except Exception as exc:
            pl_logger.warning(
                "[SKIP] secid=%s: company lookup error: %s", secid, exc,
            )
            if bond_id is not None and not is_forced:
                self._float_params_repo.upsert_not_found(
                    bond_id, _get_not_found_float_params_data()
                )
            return False

        # --- Step 2: Filter existing Markdown files ---
        # We manually filter the .md files
        # created by Pipeline 1 based on filename and header criteria.
        all_md_files: List[Path] = list(bond_data_dir.glob("*.md"))
        md_filenames: List[str] = []
        md_text_by_name: Dict[str, str] = {}
        markdown_docs: List[Dict[str, str]] = []

        for md_path in all_md_files:
            # 1. Filter by filename (Pipeline 1 saves original_name.md)
            if _filename_excluded_from_pipeline(md_path.name):
                pl_logger.info("[FILTER] Excluded by name: %s", md_path.name)
                continue

            # 2. Filter by content headers
            try:
                md_content: str = self._file_storage.read_text_file(md_path)
                if not _markdown_has_any_required_header(md_content):
                    pl_logger.info("[FILTER] Excluded by headers: %s", md_path.name)
                    continue
                md_filenames.append(md_path.name)
                md_text_by_name[md_path.name] = md_content
                markdown_docs.append({
                    "filename": md_path.name,
                    "content": md_content,
                })
            except OSError as exc:
                pl_logger.error("[ERROR] Failed to read %s: %s", md_path.name, exc)

        print(
            f"  [{secid}] After filters: {len(md_filenames)} MD files for LLM",
            flush=True,
        )

        converted: Dict[str, Any] = {
            "md_filenames": md_filenames,
            "data_dir": bond_data_dir,
            "fallback_inn": inn,
            "regnumber": regnumber,
            "search_date": date_str,
            "companies": companies,
        }


        # --- Step 3: Extract series from Markdown files (existing filter logic) ---
        series: Optional[str] = None
        for md_name in md_filenames:
            try:
                md_content: str = md_text_by_name.get(md_name, "")
                if not md_content:
                    md_path: Path = bond_data_dir / md_name
                    md_content = self._file_storage.read_text_file(md_path)
                if not markdown_has_decision_header(md_content):
                    continue
                series = extract_series_from_markdown(md_content)
                if series is not None:
                    print(f"  [{secid}] Series extracted: {series!r}", flush=True)
                    if series.isdigit():
                        print(f"  [{secid}] Series {series!r} is digits only, ignoring filter", flush=True)
                        series = None
                    break
            except OSError as exc:
                pl_logger.warning(
                    "[DOCS] secid=%s: failed to read %s: %s", secid, md_name, exc,
                )

        # --- Step 4: Load events and filter ---
        print(f"  [{secid}] Loading events", flush=True)
        event_years: List[int] = self._edisclosure_service._compute_event_years(date_str)
        events: List[Dict[str, Any]] = []
        try:
            if use_local_events:
                all_events: List[Dict[str, Any]] = (
                    self._edisclosure_service._load_events_from_local_file(
                        inn=inn, years=event_years,
                    )
                )
            else:
                all_events = []
                for ev_year in event_years:
                    year_events: List[Dict[str, Any]] = get_events_with_full_text_for_year(
                        company_id=company_id, year=ev_year,
                    )
                    all_events.extend(year_events)
            events = filter_events_by_secid_regnumber_series(
                all_events, secid or "", regnumber or "", series,
            )
            print(
                f"  [{secid}] Filtered events: {len(events)}",
                flush=True,
            )
        except Exception as exc:
            pl_logger.warning(
                "[EVENTS] secid=%s: event loading error: %s", secid, exc,
            )

        # --- Step 4.5: Filter events by event_type from DB ---
        allowed_event_types: Set[str] = {"размещение", "регистрация", "ставка купона"}
        filtered_events: List[Dict[str, Any]] = []
        for e in events:
            pseudo_guid = e.get("pseudo_guid")
            event_date = e.get("event_date")
            if pseudo_guid and event_date:
                dt_str = str(event_date)[:10]
                detail = self._event_detail_repo.get_by_guid_and_date(pseudo_guid, dt_str)
                event_name = e.get("event_name", "Без названия")
                if detail is None:
                    print(f"  [{secid}] Событие '{event_name}' ({pseudo_guid}) оставлено (нет записи в БД)", flush=True)
                    filtered_events.append(e)
                else:
                    evt_type = (detail.event_type or "").strip().lower()
                    if evt_type in allowed_event_types:
                        print(f"  [{secid}] Событие '{event_name}' ({pseudo_guid}) оставлено (тип: {evt_type!r})", flush=True)
                        filtered_events.append(e)
                    else:
                        print(f"  [{secid}] Событие '{event_name}' ({pseudo_guid}) исключено (тип: {evt_type!r})", flush=True)
            else:
                event_name = e.get("event_name", "Без названия")
                print(f"  [{secid}] Событие '{event_name}' оставлено (нет GUID/даты)", flush=True)
                filtered_events.append(e)
        events = filtered_events

        # Clean event text (existing logic)
        for e in events:
            full: str = e.get("full_text", "")
            e["text"] = clean_event_text(full)

        # Save events.json
        events_file: Path = bond_data_dir / "events.json"
        self._file_storage.save_text_file(
            events_file,
            json.dumps(
                [
                    {
                        "event_name": e.get("event_name"),
                        "event_date": e.get("event_date"),
                        "pseudo_guid": e.get("pseudo_guid"),
                        "full_text": e.get("full_text", ""),
                        "processed_text": e.get("text", ""),
                    }
                    for e in events
                ],
                ensure_ascii=False,
                indent=2,
            ),
        )

        events_for_llm: List[Dict[str, Any]] = [
            {
                "event_name": e.get("event_name"),
                "event_date": e.get("event_date"),
                "text": e.get("text", ""),
            }
            for e in events
        ]
        if not events and not markdown_docs:
            pl_logger.warning(
                "[NOT FOUND] secid=%s: no events and no documents", secid,
            )
            if bond_id is not None and not is_forced:
                self._float_params_repo.upsert_not_found(
                    bond_id, _get_not_found_float_params_data()
                )
            return False

        # Vector retrieval must be applied before sending data to LLM.
        try:
            vector_context: str = self._retrieval_pipeline.run(
                markdown_docs=markdown_docs,
                events=events_for_llm,
            )
            self._file_storage.save_text_file(
                bond_data_dir / "vector_context.md", vector_context
            )
        except Exception as exc:
            pl_logger.error(
                "[VECTOR] secid=%s: vector retrieval failed: %s", secid, exc,
                exc_info=True,
            )
            return False

        converted["events"] = []
        converted["md_filenames"] = []
        converted["vector_context"] = vector_context
        converted["use_file_upload"] = False

        # --- Step 5: LLM analysis ---
        print(
            f"  [{secid}] Sending vector context to LLM ({len(vector_context)} chars)",
            flush=True,
        )
        self._enforce_llm_rate_limit()
        try:
            analysis: Optional[GeminiBondAnalysisDTO] = (
                self._edisclosure_service._call_llm_with_retry(converted, provider)
            )
        except PromptTooLongError as exc:
            pl_logger.info(
                "[SKIP] secid=%s: prompt too long: %s", secid, exc,
            )
            print(f"  [{secid}] Skip: prompt too long", flush=True)
            return False

        if analysis is None:
            pl_logger.warning(
                "[NOT FOUND] secid=%s: LLM returned invalid response", secid,
            )
            if bond_id is not None and not is_forced:
                self._float_params_repo.upsert_not_found(
                    bond_id, _get_not_found_float_params_data()
                )
            return False

        # --- Save results ---
        print(f"  [{secid}] Saving to DB", flush=True)
        if bond_id is not None:
            self._float_params_repo.upsert(bond_id, analysis)
            pl_logger.info("[SAVED] secid=%s, bond_id=%d", secid, bond_id)
        else:
            pl_logger.warning(
                "[NOT FOUND] secid=%s: bond_id not found — save skipped", secid,
            )
            return False

        return True

    @staticmethod
    def _list_document_files(bond_dir: Path) -> List[str]:
        """List document files (PDF, DOC, DOCX, RTF) in the bond data directory.

        Returns:
            List of filenames (not full paths).
        """
        _ALLOWED_EXTENSIONS: frozenset = frozenset({".pdf", ".docx", ".doc", ".rtf"})
        if not bond_dir.is_dir():
            return []
        return [
            f.name for f in bond_dir.iterdir()
            if f.is_file() and f.suffix.lower() in _ALLOWED_EXTENSIONS
        ]

    def _enforce_llm_rate_limit(self) -> None:
        """Limits LLM call frequency: no more than 7 calls per 60 seconds."""
        now: float = time.time()
        self._llm_call_timestamps = [
            t for t in self._llm_call_timestamps if now - t < 60.0
        ]
        if len(self._llm_call_timestamps) >= 7:
            oldest: float = self._llm_call_timestamps[0]
            sleep_seconds: float = 60.0 - (now - oldest) + 0.1
            if sleep_seconds > 0:
                logger.info(
                    "[RATE LIMIT] Reached 7 requests/min limit, waiting %.1f sec",
                    sleep_seconds,
                )
                time.sleep(sleep_seconds)
            now = time.time()
            self._llm_call_timestamps = [
                t for t in self._llm_call_timestamps if now - t < 60.0
            ]
        self._llm_call_timestamps.append(time.time())


_llm_prompt_pipeline_service: Optional[LlmPromptPipelineService] = None


def get_llm_prompt_pipeline_service() -> LlmPromptPipelineService:
    """Returns singleton LlmPromptPipelineService."""
    global _llm_prompt_pipeline_service
    if _llm_prompt_pipeline_service is None:
        _llm_prompt_pipeline_service = LlmPromptPipelineService()
    return _llm_prompt_pipeline_service
