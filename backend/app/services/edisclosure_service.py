"""Сервис для интеграции с порталом раскрытия информации e-disclosure.ru.

Модуль обеспечивает автоматизированный сбор данных об облигациях, включая поиск эмитентов по ИНН,
загрузку эмиссионных документов и ленты событий.

Основные функции:
- Синхронизация идентификаторов компаний с порталом e-disclosure.

"""

import logging
import time
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from app.models.schemasDTO.llm_floatbond_dto import LLMBondAnalysisDTO
from app.repository.db.bond_float_params_repository import BondFloatParamsRepository
from app.repository.db.emitent_edisclosure_repository import EmitentEdisclosureRepository
from app.repository.db.emitents_repository import EmitentsRepository
from app.repository.files.file_storage import FileStorage
from app.core.exceptions import GeminiUnavailableError
from app.services.vector_retrieval.pipeline import RetrievalPipeline
from app.parsers.emission_documents_parser import parse_emission_documents

from app.services.llm_provider_resolution_service import LlmProviderResolutionService
from app.repository.db.emission_document_repository import EmissionDocumentRepository
from app.utils.edisclosure_utils import (
    clean_event_text,
    fetch_emission_documents_page,
    get_events_with_full_text_for_year,

)
from config.paths import EMITENT_EVENTS_JSON_DIR

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
        self._readiness: LlmProviderResolutionService = LlmProviderResolutionService()

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


_edisclosure_service: Optional[EdisclosureService] = None


def get_edisclosure_service() -> EdisclosureService:
    """Возвращает глобальный экземпляр (синглтон) сервиса EdisclosureService."""
    global _edisclosure_service
    if _edisclosure_service is None:
        _edisclosure_service = EdisclosureService()
    return _edisclosure_service
