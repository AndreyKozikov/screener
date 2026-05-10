"""Сервис для интеграции с порталом раскрытия информации e-disclosure.ru.

Модуль обеспечивает автоматизированный сбор данных об облигациях, включая поиск эмитентов по ИНН,
загрузку эмиссионных документов и ленты событий. Включает логику анализа документов
с помощью больших языковых моделей (LLM) для извлечения параметров плавающих ставок (флоатеров).

Основные функции:
- Синхронизация идентификаторов компаний с порталом e-disclosure.
- Пакетная обработка облигаций-флоатеров для актуализации их параметров.
- Оркестрация пайплайна: сбор событий -> чтение документов -> LLM анализ -> сохранение в БД.
"""

import json
import logging
import re
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from app.models.schemasDTO.gemini_dto import GeminiBondAnalysisDTO
from app.repository.db.bond_float_params_repository import BondFloatParamsRepository
from app.repository.db.emitent_edisclosure_repository import EmitentEdisclosureRepository
from app.repository.db.emitents_repository import EmitentsRepository
from app.repository.files.file_storage import FileStorage
from app.services.bonds_service import (
    get_bond_id_by_secid,
    get_emitent_inn_by_secid,
    get_emitent_moex_id_by_secid,
    get_floater_secids,
    get_reg_number_by_secid,
)
from app.services.gemini_analysis_service import (
    GEMINI_MODEL_2_5_PRO,
    GEMINI_MODEL_2_FLASH,
    GEMINI_MODEL_3_1_PRO,
    GEMINI_MODEL_3_FLASH,
    GEMINI_MODEL_FLASH,
    GEMINI_MODEL_FLASH_LITE,
    GeminiQuotaExhaustedError,
    GeminiUnavailableError,
    get_gemini_analysis_service,
)
from app.services.trading_history_service import get_trading_history_service
from app.services.vector_retrieval.pipeline import RetrievalPipeline
from app.parsers.emission_documents_parser import parse_emission_documents
from app.parsers.emission_series_parser import (
    extract_series_from_markdown,
    filter_events_by_secid_regnumber_series,
    markdown_has_decision_header,
)
from app.core.exceptions import PromptTooLongError
from app.services.llm_provider_readiness_service import LlmProviderReadinessService
from app.repository.db.emission_document_repository import EmissionDocumentRepository
from app.utils.edisclosure_utils import (
    clean_event_text,
    fetch_emission_documents_page,
    get_events_with_full_text_for_year,
    search_company_by_inn,
)
from config.paths import EMITENT_EVENTS_JSON_DIR
from config.settings import settings

logger: logging.Logger = logging.getLogger(__name__)

_DEFAULT_DATE: str = "2025-04-24"

_PROCESSING_STATE_KEY: str = "__processing_state"


def _get_not_found_float_params_data() -> Dict[str, Any]:
    """Генерирует структуру данных по умолчанию для случаев, когда параметры не найдены."""
    return {
        "is_find": 0,
        "base_indicator_code": "",
        "spread": None,
        "coupon_frequency_days": None,
        "lookback_period": None,
        "averaging_period": None,
        "formula_raw": None,
        "rate_determination_rule": None,
        "calculation_type": None,
        "rounding_precision": None,
        "key_rate_method": None,
        "lookback_type": None,
        "year_base": None,
        "is_daily_accrual": False,
        "offset_days": None,
        "offset_calendar": None,
        "day_count": None,
        "fallback": None,
        "accrual_type": None,
        "interest_compounding": False,
        "placement_date": None,
        "underwriter": None,
        "floor_rate": None,
        "cap_rate": None,
        "extra_indicators": None,
        "condition_logic": None,
        "observation_type": None,
        "reference_period_desc": None,
    }


class SkipBondException(Exception):
    """Исключение: облигация пропущена пайплайном."""


_DATA_DIR: Path = Path(__file__).resolve().parent.parent / "data"

# Фразы в имени файла (без учёта регистра), при наличии которых файл не отправляется на конвертацию.
_FILENAME_EXCLUDE_PHRASES: Tuple[str, ...] = (
    "Отчетность МСФО",
    "Отчетность РСБУ",
    "Отчетность",
    "МСФО",
    "РСБУ",
    "Проспект",
    "Сертификат",
    "vector_context",
)

# Обязательные заголовки в Markdown-файле (без учёта регистра).
_REQUIRED_HEADERS: Tuple[str, ...] = (
    "ДОКУМЕНТ, СОДЕРЖАЩИЙ УСЛОВИЯ РАЗМЕЩЕНИЯ ЦЕННЫХ БУМАГ",
    "РЕШЕНИЕ О ВЫПУСКЕ ЦЕННЫХ БУМАГ",
    "Уведомление об итогах выпуска",
)


def _get_floaters_pipeline_logger() -> logging.Logger:
    """Инициализирует и возвращает специализированный логгер для пайплайна флоатеров."""
    from config.paths import BACKEND_DIR

    log_dir: Path = BACKEND_DIR / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    logger_name: str = "floaters_pipeline"
    fl_logger: logging.Logger = logging.getLogger(logger_name)
    if fl_logger.handlers:
        return fl_logger

    fl_logger.setLevel(logging.INFO)
    log_file: Path = log_dir / f"floaters_pipeline_{datetime.now().strftime('%Y-%m-%d')}.log"
    fh: logging.FileHandler = logging.FileHandler(log_file, encoding="utf-8")
    fh.setLevel(logging.INFO)
    fmt: logging.Formatter = logging.Formatter(
        "%(asctime)s - %(levelname)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    )
    fh.setFormatter(fmt)
    fl_logger.addHandler(fh)
    fl_logger.propagate = False
    return fl_logger


class EdisclosureService:
    """Сервис-координатор процессов сбора данных и LLM-анализа документов e-disclosure."""

    def __init__(self) -> None:
        self._file_storage: FileStorage = FileStorage()
        self._float_params_repo: BondFloatParamsRepository = BondFloatParamsRepository()
        self._emitents_repo: EmitentsRepository = EmitentsRepository()
        self._emitent_edisclosure_repo: EmitentEdisclosureRepository = EmitentEdisclosureRepository()
        self._emission_doc_repo: EmissionDocumentRepository = EmissionDocumentRepository()
        self._retrieval_pipeline: RetrievalPipeline = RetrievalPipeline()
        self._llm_call_timestamps: List[float] = []
        self._readiness: LlmProviderReadinessService = LlmProviderReadinessService()

    def _resolve_company_id_by_inn(self, inn: str) -> Tuple[int, List[Dict[str, Any]]]:
        """Определяет уникальный идентификатор компании на портале e-disclosure."""
        emitent_id: Optional[int] = self._emitents_repo.get_emitent_id_by_inn(inn)
        edisclosure_id: Optional[int] = None
        if emitent_id is not None:
            edisclosure_id = self._emitent_edisclosure_repo.get_edisclosure_id_by_emitent_id(
                emitent_id
            )
        if edisclosure_id is not None:
            company_id: int = int(edisclosure_id)
            return company_id, [{"id": company_id, "name": ""}]

        companies: List[Dict[str, Any]] = search_company_by_inn(inn)
        if not companies:
            raise ValueError(f"Компания с ИНН {inn} не найдена на e-disclosure.ru")
        raw_id: Any = companies[0].get("id")
        if raw_id is None:
            raise ValueError("Не удалось получить ID компании из ответа e-disclosure")
        try:
            company_id = int(raw_id)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                "Не удалось получить ID компании из ответа e-disclosure"
            ) from exc
        return company_id, companies

    def _get_analysis_service(self, provider: str) -> Any:
        """Фабричный метод для получения экземпляра сервиса LLM-анализа."""
        if provider == "openrouter":
            from app.services.openrouter_analysis_service import get_openrouter_analysis_service
            return get_openrouter_analysis_service()
        if provider == "local":
            from app.services.local_analysis_service import get_local_analysis_service
            return get_local_analysis_service()
        if provider == "openai-gpt-5.1":
            from app.services.openai_analysis_service import get_openai_analysis_service
            return get_openai_analysis_service()
        return get_gemini_analysis_service()

    def _get_gemini_model(self, provider: str) -> Optional[str]:
        """Маппинг строковых имен провайдеров в технические идентификаторы моделей Gemini."""
        if provider == "gemini":
            return GEMINI_MODEL_FLASH_LITE
        if provider == "gemini-flash":
            return GEMINI_MODEL_FLASH
        if provider == "gemini-2.5-pro":
            return GEMINI_MODEL_2_5_PRO
        if provider == "gemini-2-flash":
            return GEMINI_MODEL_2_FLASH
        if provider == "gemini-3-flash":
            return GEMINI_MODEL_3_FLASH
        if provider == "gemini-3.1-pro":
            return GEMINI_MODEL_3_1_PRO
        return None

    def _call_llm_with_retry(
        self,
        converted: Dict[str, Any],
        provider: str,
    ) -> Optional[GeminiBondAnalysisDTO]:
        """Выполняет вызов LLM с механизмом повторных попыток."""
        max_attempts: int = 3
        delays_sec: Tuple[int, ...] = (20, 60)
        gemini_model: Optional[str] = self._get_gemini_model(provider)
        for attempt in range(max_attempts):
            try:
                if gemini_model is not None:
                    return self._get_analysis_service("gemini").analyze(
                        converted, model=gemini_model
                    )
                return self._get_analysis_service(provider).analyze(converted)
            except GeminiUnavailableError as exc:
                if attempt < max_attempts - 1:
                    delay: int = delays_sec[attempt]
                    time.sleep(delay)
                else:
                    raise
        return None

    def get_accrued_income_by_secid(
        self,
        secid: str,
        provider: Optional[str] = None,
        use_file_upload: bool = False,
        use_local_events: bool = False,
    ) -> Dict[str, str]:
        """Запускает процесс анализа параметров флоатера для конкретной облигации по её SECID."""
        secid = (secid or "").strip()
        if not secid:
            raise ValueError("SECID не указан")

        resolved_provider: str = self._readiness.resolve_provider(provider)

        inn = get_emitent_inn_by_secid(secid)
        if not inn:
            raise ValueError(
                f"ИНН эмитента для облигации {secid} не найден в БД."
            )

        regnumber = get_reg_number_by_secid(secid)
        emitent_moex_id = get_emitent_moex_id_by_secid(secid)

        trading_history_service = get_trading_history_service()
        first_tradedate = trading_history_service.get_first_tradedate(secid)
        date_str = (
            first_tradedate.isoformat()
            if first_tradedate is not None
            else _DEFAULT_DATE
        )

        bond_data_dir: Path = _DATA_DIR / secid
        bond_data_dir.mkdir(parents=True, exist_ok=True)

        try:
            analysis = self._get_accrued_income_by_inn(
                inn=inn,
                date=date_str,
                regnumber=regnumber,
                emitent_moex_id=emitent_moex_id,
                provider=resolved_provider,
                secid=secid,
                use_file_upload=use_file_upload,
                use_local_events=use_local_events,
            )
        except SkipBondException as exc:
            return {"status": "skipped", "detail": str(exc)}
        except PromptTooLongError as exc:
            return {"status": "skipped", "detail": str(exc)}

        if analysis is None:
            return {"status": "error", "detail": "Ошибка валидации ответа LLM"}

        bond_id: Optional[int] = get_bond_id_by_secid(secid)
        if bond_id is not None:
            self._float_params_repo.upsert(bond_id, analysis)
        
        return {"status": "ok"}

    def _load_events_from_local_file(
        self,
        inn: str,
        years: List[int],
    ) -> List[Dict[str, Any]]:
        """Загружает и предварительно обрабатывает ленту событий из локального кэша."""
        events_file: Path = EMITENT_EVENTS_JSON_DIR / f"{inn.strip()}.json"
        if not events_file.exists():
            return []

        try:
            raw_data: Any = self._file_storage.read_json(events_file)
        except Exception:
            return []

        if not isinstance(raw_data, dict):
            return []

        years_str: Set[str] = {str(y) for y in years}

        all_events: List[Dict[str, Any]] = []
        for year_key, events_list in raw_data.items():
            if year_key == _PROCESSING_STATE_KEY:
                continue
            if year_key not in years_str:
                continue
            if not isinstance(events_list, list):
                continue
            for ev in events_list:
                if not isinstance(ev, dict):
                    continue
                all_events.append(ev)

        dated_events: List[tuple] = []
        for ev in all_events:
            event_date_str: Optional[str] = ev.get("event_date")
            if not event_date_str or not str(event_date_str).strip():
                continue
            try:
                ev_date: date = datetime.strptime(
                    str(event_date_str)[:10], "%Y-%m-%d"
                ).date()
            except (ValueError, TypeError):
                continue
            dated_events.append((ev_date, ev))

        dated_events.sort(key=lambda x: x[0], reverse=True)

        result: List[Dict[str, Any]] = []
        for _, ev in dated_events:
            full_text: str = ev.get("full_text", "")
            processed_text: str = clean_event_text(full_text)
            result.append({
                "event_name": ev.get("event_name", ""),
                "event_date": ev.get("event_date"),
                "full_text": full_text,
                "text": processed_text,
            })
        return result

    @staticmethod
    def _compute_event_years(first_tradedate_str: str) -> List[int]:
        """Определяет временной диапазон для поиска документов."""
        try:
            trade_date: date = datetime.strptime(first_tradedate_str, "%Y-%m-%d").date()
        except (ValueError, TypeError):
            current_year: int = date.today().year
            return [current_year]

        trade_year: int = trade_date.year
        current_year = date.today().year
        event_years: List[int] = [trade_year]
        if trade_year < current_year:
            event_years.append(trade_year + 1)
        return event_years

    def _list_and_filter_local_documents(self, bond_data_dir: Path) -> List[str]:
        """Выполняет поиск и фильтрацию Markdown-документов в локальной директории."""
        if not bond_data_dir.is_dir():
            return []

        all_md_files: List[Path] = list(bond_data_dir.glob("*.md"))
        md_filenames: List[str] = []

        for md_path in all_md_files:
            filename: str = md_path.name
            if any(phrase.lower() in filename.lower() for phrase in _FILENAME_EXCLUDE_PHRASES):
                continue

            try:
                content: str = self._file_storage.read_text_file(md_path)
                if not any(header.lower() in content.lower() for header in _REQUIRED_HEADERS):
                    continue
                md_filenames.append(filename)
            except Exception:
                pass
        return md_filenames

    def _get_accrued_income_by_inn(
        self,
        inn: str,
        date: str = "2025-04-24",
        regnumber: Optional[str] = None,
        emitent_moex_id: Optional[int] = None,
        provider: str = "gemini",
        secid: str = "",
        use_file_upload: bool = False,
        use_local_events: bool = False,
    ) -> Optional[GeminiBondAnalysisDTO]:
        """Внутренний метод реализации пайплайна анализа по ИНН."""
        bond_data_dir: Path = _DATA_DIR / (secid or "unknown")
        bond_data_dir.mkdir(parents=True, exist_ok=True)

        company_id, companies = self._resolve_company_id_by_inn(inn)
        md_filenames: List[str] = self._list_and_filter_local_documents(bond_data_dir)
        
        series: Optional[str] = None
        markdown_docs: List[Dict[str, str]] = []
        for md_name in md_filenames:
            try:
                md_path: Path = bond_data_dir / md_name
                md_content: str = self._file_storage.read_text_file(md_path)
                markdown_docs.append({
                    "filename": md_name,
                    "content": md_content,
                })
                if not markdown_has_decision_header(md_content):
                    continue
                series = extract_series_from_markdown(md_content)
                if series is not None:
                    break
            except OSError:
                pass

        event_years: List[int] = self._compute_event_years(date)
        if use_local_events:
            all_events: List[Dict[str, Any]] = self._load_events_from_local_file(
                inn=inn,
                years=event_years,
            )
        else:
            all_events = []
            for ev_year in event_years:
                year_events: List[Dict[str, Any]] = get_events_with_full_text_for_year(
                    company_id=company_id,
                    year=ev_year,
                )
                all_events.extend(year_events)
        events: List[Dict[str, Any]] = filter_events_by_secid_regnumber_series(
            all_events, secid or "", regnumber or "", series
        )

        for e in events:
            full: str = e.get("full_text", "")
            e["text"] = clean_event_text(full)

        events_file: Path = bond_data_dir / "events.json"
        self._file_storage.save_text_file(
            events_file,
            json.dumps(
                [
                    {
                        "event_name": e.get("event_name"),
                        "event_date": e.get("event_date"),
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
            {"event_name": e.get("event_name"), "event_date": e.get("event_date"), "text": e.get("text", "")}
            for e in events
        ]
        if not events and not markdown_docs:
            return None

        try:
            vector_context: str = self._retrieval_pipeline.run(
                markdown_docs=markdown_docs,
                events=events_for_llm,
            )
            self._file_storage.save_text_file(
                bond_data_dir / "vector_context.md", vector_context
            )
        except Exception:
            return None

        converted: Dict[str, Any] = {
            "companies": companies,
            "events": [],
            "regnumber": regnumber,
            "search_date": date,
            "doc_filenames": [],
            "md_filenames": [],
            "vector_context": vector_context,
            "data_dir": bond_data_dir,
            "fallback_inn": inn,
            "use_file_upload": False,
        }

        return self._call_llm_with_retry(converted, provider)

    def update_all_floaters(
        self,
        provider: Optional[str] = None,
        limit: Optional[int] = None,
        use_file_upload: bool = False,
        rating: Optional[str] = None,
        use_local_events: bool = False,
    ) -> None:
        """Запускает пакетную обработку всех известных облигаций-флоатеров."""
        resolved_provider: str = self._readiness.resolve_provider(provider)
        fl_logger: logging.Logger = _get_floaters_pipeline_logger()

        all_secids: List[str] = get_floater_secids(rating=rating)
        existing_bond_ids: Set[int] = self._float_params_repo.get_existing_bond_ids()

        secids: List[str] = []
        for sid in all_secids:
            bid: Optional[int] = get_bond_id_by_secid(sid)
            if bid is not None and bid in existing_bond_ids:
                continue
            secids.append(sid)

        if limit is not None:
            secids = secids[:limit]

        processed: int = 0
        saved: int = 0
        not_found_secids: List[str] = []
        quota_exhausted_error: Optional[GeminiQuotaExhaustedError] = None

        for secid in secids:
            processed += 1
            try:
                success: bool = self._process_single_floater(
                    secid,
                    fl_logger,
                    provider=resolved_provider,
                    use_file_upload=use_file_upload,
                    use_local_events=use_local_events,
                )
                if success:
                    saved += 1
                else:
                    not_found_secids.append(secid)
            except GeminiQuotaExhaustedError as exc:
                quota_exhausted_error = exc
                break
            except GeminiUnavailableError:
                raise
            except Exception as exc:
                not_found_secids.append(secid)

        if quota_exhausted_error is not None:
            raise quota_exhausted_error

    def populate_emitent_edisclosure(self) -> Dict[str, int]:
        """Синхронизирует локальный список эмитентов с базой портала e-disclosure."""
        _delay: float = 2.0
        emitents: List[Dict[str, Any]] = self._emitents_repo.get_emitents_with_inn()
        existing_ids: Set[int] = self._emitent_edisclosure_repo.get_existing_emitent_ids()

        to_process: List[Dict[str, Any]] = [
            e for e in emitents if e["id"] not in existing_ids
        ]
        saved: int = 0
        skipped: int = 0

        for emitent in to_process:
            emitent_id: int = emitent["id"]
            inn: str = emitent["inn"]

            try:
                companies: List[Dict[str, Any]] = search_company_by_inn(inn)
                if not companies:
                    skipped += 1
                    time.sleep(_delay)
                    continue

                raw_id: Optional[Any] = companies[0].get("id")
                if raw_id is None:
                    skipped += 1
                    time.sleep(_delay)
                    continue

                edisclosure_id: int = int(raw_id)
                self._emitent_edisclosure_repo.upsert_mapping(emitent_id, edisclosure_id)
                saved += 1
            except Exception:
                skipped += 1

            time.sleep(_delay)

        return {
            "total_emitents": len(emitents),
            "already_in_table": len(existing_ids),
            "to_process": len(to_process),
            "saved": saved,
            "skipped": skipped,
        }

    def fetch_emission_documents(
        self, limit: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Загружает метаданные всех доступных эмиссионных документов для эмитентов."""
        _delay: float = 1.5
        emitents: List[Dict[str, Any]] = (
            self._emitent_edisclosure_repo.get_emitents_ordered_by_missing_docs(limit)
        )
        processed: int = 0
        total_docs_added: int = 0
        empty_count: int = 0

        for emitent in emitents:
            emitent_edisclosure_id: int = emitent["id"]
            edisclosure_id: int = emitent["edisclosure_id"]

            try:
                html: str = fetch_emission_documents_page(edisclosure_id)
                docs: List[Dict[str, Optional[str]]] = parse_emission_documents(html)

                if not docs:
                    empty_count += 1
                else:
                    inserted: int = self._emission_doc_repo.insert_batch(
                        emitent_edisclosure_id, docs,
                    )
                    total_docs_added += inserted
            except Exception:
                empty_count += 1

            processed += 1
            time.sleep(_delay)

        return {
            "processed": processed,
            "total_docs_added": total_docs_added,
            "empty_count": empty_count,
        }

    def _process_single_floater(
        self,
        secid: str,
        fl_logger: logging.Logger,
        provider: str = "gemini",
        use_file_upload: bool = False,
        use_local_events: bool = False,
    ) -> bool:
        """Реализует полный цикл обработки (пайплайн) для одной облигации-флоатера."""
        bond_data_dir: Path = _DATA_DIR / secid
        bond_data_dir.mkdir(parents=True, exist_ok=True)

        inn: Optional[str] = get_emitent_inn_by_secid(secid)
        if not inn:
            bond_id: Optional[int] = get_bond_id_by_secid(secid)
            if bond_id is not None:
                self._float_params_repo.upsert_not_found(bond_id, _get_not_found_float_params_data())
            return False

        regnumber: Optional[str] = get_reg_number_by_secid(secid)
        emitent_moex_id: Optional[int] = get_emitent_moex_id_by_secid(secid)
        bond_id = get_bond_id_by_secid(secid)

        trading_service = get_trading_history_service()
        first_tradedate = trading_service.get_first_tradedate(secid)
        date_str: str = (
            first_tradedate.isoformat() if first_tradedate is not None else _DEFAULT_DATE
        )

        try:
            company_id, companies = self._resolve_company_id_by_inn(inn)
        except Exception:
            if bond_id is not None:
                self._float_params_repo.upsert_not_found(
                    bond_id, _get_not_found_float_params_data()
                )
            return False

        md_filenames_batch: List[str] = self._list_and_filter_local_documents(bond_data_dir)
        
        series: Optional[str] = None
        markdown_docs_batch: List[Dict[str, str]] = []
        for md_name in md_filenames_batch:
            try:
                md_path_batch: Path = bond_data_dir / md_name
                md_content_batch: str = self._file_storage.read_text_file(md_path_batch)
                markdown_docs_batch.append({
                    "filename": md_name,
                    "content": md_content_batch,
                })
                if not markdown_has_decision_header(md_content_batch):
                    continue
                series = extract_series_from_markdown(md_content_batch)
                if series is not None:
                    break
            except OSError:
                pass

        event_years: List[int] = self._compute_event_years(date_str)
        events: List[Dict[str, Any]] = []
        try:
            if use_local_events:
                all_events_batch: List[Dict[str, Any]] = self._load_events_from_local_file(
                    inn=inn,
                    years=event_years,
                )
            else:
                all_events_batch = []
                for ev_year in event_years:
                    year_events: List[Dict[str, Any]] = get_events_with_full_text_for_year(
                        company_id=company_id,
                        year=ev_year,
                    )
                    all_events_batch.extend(year_events)
            events = filter_events_by_secid_regnumber_series(
                all_events_batch, secid or "", regnumber or "", series
            )
        except Exception:
            pass

        for e in events:
            full_batch: str = e.get("full_text", "")
            e["text"] = clean_event_text(full_batch)

        events_file_batch: Path = bond_data_dir / "events.json"
        self._file_storage.save_text_file(
            events_file_batch,
            json.dumps(
                [
                    {
                        "event_name": e.get("event_name"),
                        "event_date": e.get("event_date"),
                        "full_text": e.get("full_text", ""),
                        "processed_text": e.get("text", ""),
                    }
                    for e in events
                ],
                ensure_ascii=False,
                indent=2,
            ),
        )
        events_for_llm_batch: List[Dict[str, Any]] = [
            {"event_name": e.get("event_name"), "event_date": e.get("event_date"), "text": e.get("text", "")}
            for e in events
        ]
        if not events and not markdown_docs_batch:
            if bond_id is not None:
                self._float_params_repo.upsert_not_found(bond_id, _get_not_found_float_params_data())
            return False

        try:
            vector_context_batch: str = self._retrieval_pipeline.run(
                markdown_docs=markdown_docs_batch,
                events=events_for_llm_batch,
            )
            self._file_storage.save_text_file(
                bond_data_dir / "vector_context.md", vector_context_batch
            )
        except Exception:
            return False

        converted: Dict[str, Any] = {
            "companies": companies,
            "events": [],
            "regnumber": regnumber,
            "search_date": date_str,
            "doc_filenames": [],
            "md_filenames": [],
            "vector_context": vector_context_batch,
            "data_dir": bond_data_dir,
            "fallback_inn": inn,
            "use_file_upload": False,
        }

        self._enforce_llm_rate_limit()
        try:
            analysis: Optional[GeminiBondAnalysisDTO] = self._call_llm_with_retry(converted, provider)
        except PromptTooLongError:
            return False

        if analysis is None:
            if bond_id is not None:
                self._float_params_repo.upsert_not_found(bond_id, _get_not_found_float_params_data())
            return False

        if bond_id is not None:
            self._float_params_repo.upsert(bond_id, analysis)
        
        return True

    def _enforce_llm_rate_limit(self) -> None:
        """Обеспечивает соблюдение ограничений на частоту вызовов LLM API."""
        now: float = time.time()
        self._llm_call_timestamps = [
            t for t in self._llm_call_timestamps if now - t < 60.0
        ]
        if len(self._llm_call_timestamps) >= 7:
            oldest: float = self._llm_call_timestamps[0]
            sleep_seconds: float = 60.0 - (now - oldest) + 0.1
            if sleep_seconds > 0:
                time.sleep(sleep_seconds)
            now = time.time()
            self._llm_call_timestamps = [
                t for t in self._llm_call_timestamps if now - t < 60.0
            ]
        self._llm_call_timestamps.append(time.time())


_edisclosure_service: Optional[EdisclosureService] = None


def get_edisclosure_service() -> EdisclosureService:
    """Возвращает глобальный экземпляр (синглтон) сервиса EdisclosureService."""
    global _edisclosure_service
    if _edisclosure_service is None:
        _edisclosure_service = EdisclosureService()
    return _edisclosure_service
