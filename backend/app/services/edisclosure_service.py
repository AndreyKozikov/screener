"""Сервис для работы с e-disclosure.ru.

Содержит логику вызова методов из edisclosure_utils: получение company_id из БД
(emitent_edisclosure) или поиск компаний по ИНН на e-disclosure, поиск событий
по регистрационному номеру облигации и скачивание эмиссионных документов из
таблицы emission_documents (по ИНН и рег. номеру) с распаковкой ZIP в папку по secid.
Эндпоинт вызывает get_accrued_income_by_secid(secid), который после получения
результата анализа от Gemini сохраняет данные в БД через BondFloatParamsRepository.

Метод update_all_floaters() обрабатывает все облигации вида «флоатер» (bond_kind=8)
в пакетном режиме с ограничением на количество запросов к LLM (7 в минуту).
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
from app.services.pdf_conversion_service import get_pdf_conversion_service
from app.services.trading_history_service import get_trading_history_service
from app.parsers.emission_documents_parser import parse_emission_documents
from app.parsers.emission_series_parser import (
    extract_series_from_markdown,
    filter_events_by_secid_regnumber_series,
    markdown_has_decision_header,
)
from app.core.exceptions import PdfConversionConnectionError
from app.services.llm_provider_readiness_service import LlmProviderReadinessService
from app.repository.db.emission_document_repository import EmissionDocumentRepository
from app.utils.edisclosure_utils import (
    clean_event_text,
    download_emission_file,
    extract_zip_to_dir,
    fetch_emission_documents_page,
    fetch_emitent_year_events_unfiltered,
    fetch_events_page_json_only,
    find_events_by_reg_number,
    find_latest_event_metadata_across_years,
    get_events_with_full_text,
    list_company_portal_event_years,
    merge_emitent_event_lists,
    parse_latest_event_from_emitent_file_payload,
    search_company_by_inn,
)
from config.paths import EMITENT_EVENTS_JSON_DIR
from config.settings import settings

logger: logging.Logger = logging.getLogger(__name__)

_DEFAULT_DATE: str = "2025-04-24"


def _get_not_found_float_params_data() -> Dict[str, Any]:
    """Возвращает структуру данных «данные не найдены» для bond_float_params.

    Формируется в сервисе (бизнес-логика); репозиторий только сохраняет
    переданную структуру. is_find=0, base_indicator_code="" (NOT NULL),
    остальные поля — NULL/False.
    """
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
    """Исключение: облигация пропущена пайплайном (например, в архиве есть не-PDF файлы)."""


_DATA_DIR: Path = Path(__file__).resolve().parent.parent / "data"


def _get_floaters_pipeline_logger() -> logging.Logger:
    """Возвращает логгер, пишущий события пайплайна флоатеров в отдельный файл."""
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
    """Сервис для получения данных с e-disclosure.ru.

    Оркестрирует получение company_id из emitent_edisclosure или search_company_by_inn,
    find_events_by_reg_number и скачивание документов из emission_documents с e-disclosure.
    Использует bonds_service для получения ИНН и регномера по secid,
    TradingHistoryService — для наименьшей даты из истории торгов.
    """

    def __init__(self) -> None:
        self._file_storage: FileStorage = FileStorage()
        self._float_params_repo: BondFloatParamsRepository = BondFloatParamsRepository()
        self._emitents_repo: EmitentsRepository = EmitentsRepository()
        self._emitent_edisclosure_repo: EmitentEdisclosureRepository = EmitentEdisclosureRepository()
        self._emission_doc_repo: EmissionDocumentRepository = EmissionDocumentRepository()
        self._llm_call_timestamps: List[float] = []
        self._readiness: LlmProviderReadinessService = LlmProviderReadinessService()

    def _resolve_company_id_by_inn(self, inn: str) -> Tuple[int, List[Dict[str, Any]]]:
        """Возвращает id компании на e-disclosure.ru и список компаний для пайплайна анализа.

        Сначала emitent_edisclosure по ИНН, иначе поиск по API e-disclosure.
        """
        print(
            f"[E-DISCLOSURE RESOLVE] Старт резолва company_id по ИНН={inn}",
            flush=True,
        )
        emitent_id: Optional[int] = self._emitents_repo.get_emitent_id_by_inn(inn)
        if emitent_id is not None:
            print(
                f"[E-DISCLOSURE RESOLVE] emitent_id найден в локальной БД: {emitent_id}",
                flush=True,
            )
        else:
            print(
                "[E-DISCLOSURE RESOLVE] emitent_id в локальной БД не найден",
                flush=True,
            )
        edisclosure_id: Optional[int] = None
        if emitent_id is not None:
            edisclosure_id = self._emitent_edisclosure_repo.get_edisclosure_id_by_emitent_id(
                emitent_id
            )
            if edisclosure_id is not None:
                print(
                    f"[E-DISCLOSURE RESOLVE] edisclosure_id найден в таблице маппинга: {edisclosure_id}",
                    flush=True,
                )
            else:
                print(
                    "[E-DISCLOSURE RESOLVE] edisclosure_id в таблице маппинга отсутствует",
                    flush=True,
                )
        else:
            print(
                "[E-DISCLOSURE RESOLVE] Шаг маппинга edisclosure_id пропущен (нет emitent_id)",
                flush=True,
            )
        if edisclosure_id is not None:
            company_id: int = int(edisclosure_id)
            print(
                f"[E-DISCLOSURE RESOLVE] Успех: финальный company_id={company_id}",
                flush=True,
            )
            logger.info(
                "[E-DISCLOSURE] company_id=%s взят из таблицы emitent_edisclosure (ИНН=%s)",
                company_id, inn,
            )
            return company_id, [{"id": company_id, "name": ""}]

        print(
            "[E-DISCLOSURE RESOLVE] Переход к fallback: поиск компании через API e-disclosure",
            flush=True,
        )
        logger.info(
            "[E-DISCLOSURE] → POST https://www.e-disclosure.ru/api/search/companies | ИНН=%s",
            inn,
        )
        companies: List[Dict[str, Any]] = search_company_by_inn(inn)
        print(
            f"[E-DISCLOSURE RESOLVE] API вернуло компаний: {len(companies)}",
            flush=True,
        )
        if not companies:
            print(
                f"[E-DISCLOSURE RESOLVE] Ошибка перед raise: компания с ИНН={inn} не найдена",
                flush=True,
            )
            raise ValueError(f"Компания с ИНН {inn} не найдена на e-disclosure.ru")
        raw_id: Any = companies[0].get("id")
        print(
            "[E-DISCLOSURE RESOLVE] Выбрана первая компания: "
            f"id={raw_id}, name={companies[0].get('name')}",
            flush=True,
        )
        if raw_id is None:
            print(
                "[E-DISCLOSURE RESOLVE] Ошибка перед raise: у первой компании отсутствует id",
                flush=True,
            )
            raise ValueError("Не удалось получить ID компании из ответа e-disclosure")
        try:
            company_id = int(raw_id)
        except (TypeError, ValueError) as exc:
            print(
                f"[E-DISCLOSURE RESOLVE] Ошибка перед raise: id компании невалиден для int: {raw_id}",
                flush=True,
            )
            raise ValueError(
                "Не удалось получить ID компании из ответа e-disclosure"
            ) from exc
        print(
            f"[E-DISCLOSURE RESOLVE] Успех: финальный company_id={company_id}",
            flush=True,
        )
        logger.info(
            "[E-DISCLOSURE] Найдено компаний: %d, company_id=%s, название=%s",
            len(companies), company_id, companies[0].get("name"),
        )
        return company_id, companies

    def _get_analysis_service(self, provider: str) -> Any:
        """Возвращает сервис LLM-анализа по имени провайдера.

        Args:
            provider: Имя провайдера: gemini (2.5 Flash Lite), gemini-flash (2.5 Flash),
                gemini-2.5-pro, gemini-2-flash, gemini-3-flash, gemini-3.1-pro,
                openai-gpt-5.1, openrouter или local.

        Returns:
            Экземпляр сервиса анализа с методом analyze().
        """
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
        """Возвращает идентификатор модели Gemini для провайдера или None (не Gemini)."""
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
        """Вызывает LLM-анализ с повторами при 503 UNAVAILABLE.

        При первой 503 — пауза 20 сек и повтор; при второй — пауза 60 сек и повтор;
        при третьей — исключение GeminiUnavailableError (остановка пайплайна).
        """
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
                    logger.warning(
                        "[GEMINI] 503 UNAVAILABLE (попытка %d/%d), пауза %d сек...",
                        attempt + 1, max_attempts, delay,
                    )
                    print(
                        f"  [GEMINI] 503 UNAVAILABLE, пауза {delay} сек перед повтором...",
                        flush=True,
                    )
                    time.sleep(delay)
                else:
                    logger.error(
                        "[GEMINI] 503 UNAVAILABLE после %d попыток. Остановка пайплайна.",
                        max_attempts,
                    )
                    raise
        return None

    def get_accrued_income_by_secid(
        self,
        secid: str,
        provider: Optional[str] = None,
        use_file_upload: bool = False,
    ) -> Dict[str, str]:
        """Получает данные флоатера по SECID, анализирует через LLM и сохраняет в БД.

        1. Получает ИНН эмитента и рег. номер облигации по secid из БД.
        2. Получает наименьшую дату из таблицы истории торгов.
        3. Вызывает _get_accrued_income_by_inn для анализа через LLM.
        4. Если LLM вернул None (ошибка валидации) — пропускает запись в БД
           и возвращает {"status": "error", "detail": "..."}.
        5. Сохраняет результат анализа в БД через BondFloatParamsRepository.
        6. Возвращает {"status": "ok"}.

        Args:
            secid: Идентификатор ценной бумаги.
            provider: Провайдер LLM (gemini, openai-gpt-5.1, openrouter, local).
                None или пустая строка — режим AUTO (проба удалённых провайдеров).
            use_file_upload: Если True — для Gemini/OpenAI подавать в модель
                оригинальные файлы (PDF, Word) через Files API; иначе — только Markdown в промпте.

        Returns:
            Словарь {"status": "ok"} или {"status": "error", "detail": "..."}.

        Raises:
            ValueError: ИНН эмитента не найден в БД.
        """
        secid = (secid or "").strip()
        if not secid:
            raise ValueError("SECID не указан")

        resolved_provider: str = self._readiness.resolve_provider(provider)

        logger.info("=" * 60)
        logger.info("[PIPELINE START] Получен запрос от фронтенда: secid=%s", secid)

        inn = get_emitent_inn_by_secid(secid)
        if not inn:
            raise ValueError(
                f"ИНН эмитента для облигации {secid} не найден в БД. "
                "Проверьте наличие данных об эмитенте."
            )

        regnumber = get_reg_number_by_secid(secid)
        emitent_moex_id = get_emitent_moex_id_by_secid(secid)
        logger.info(
            "[DB] Данные из БД: ИНН=%s, рег.номер=%s, MOEX emitent_id=%s",
            inn, regnumber, emitent_moex_id,
        )

        trading_history_service = get_trading_history_service()
        first_tradedate = trading_history_service.get_first_tradedate(secid)
        date_str = (
            first_tradedate.isoformat()
            if first_tradedate is not None
            else _DEFAULT_DATE
        )
        logger.info(
            "[TRADING HISTORY] Первая дата торгов: %s → граничная дата событий: %s",
            first_tradedate, date_str,
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
            )
        except SkipBondException as exc:
            logger.info(
                "[PIPELINE SKIP] secid=%s: %s",
                secid, exc,
            )
            return {"status": "skipped", "detail": str(exc)}
        except PdfConversionConnectionError as exc:
            logger.error(
                "[PIPELINE ERROR] secid=%s: ошибка подключения к pdf2md: %s",
                secid, exc,
            )
            return {"status": "error", "detail": str(exc)}

        if analysis is None:
            logger.warning(
                "[PIPELINE] Анализ Gemini вернул None — запись в БД пропущена. secid=%s",
                secid,
            )
            return {"status": "error", "detail": "Ошибка валидации ответа LLM"}

        bond_id: Optional[int] = get_bond_id_by_secid(secid)
        if bond_id is not None:
            logger.info("[DB SAVE] Сохранение параметров флоатера: bond_id=%d", bond_id)
            self._float_params_repo.upsert(bond_id, analysis)
            logger.info("[DB SAVE] Успешно сохранено: bond_id=%d", bond_id)
        else:
            logger.warning("[DB SAVE] bond_id не найден для secid=%s — запись пропущена", secid)

        logger.info("[PIPELINE DONE] secid=%s → статус: ok", secid)
        logger.info("=" * 60)
        return {"status": "ok"}

    @staticmethod
    def _all_extracted_files_are_convertible(filenames: List[str]) -> bool:
        """True, если все имена файлов имеют расширение, допустимое для конвертации через pdf2md.

        Допустимые расширения (без учёта регистра): .pdf, .docx, .doc, .rtf.
        """
        if not filenames:
            return True
        _ALLOWED_EXTENSIONS: frozenset = frozenset({".pdf", ".docx", ".doc", ".rtf"})
        return all(Path(f).suffix.lower() in _ALLOWED_EXTENSIONS for f in filenames)

    def _get_accrued_income_by_inn(
        self,
        inn: str,
        date: str = "2025-04-24",
        regnumber: Optional[str] = None,
        emitent_moex_id: Optional[int] = None,
        provider: str = "gemini",
        secid: str = "",
        use_file_upload: bool = False,
    ) -> Optional[GeminiBondAnalysisDTO]:
        """Получает данные компании по ИНН и выполняет полный пайплайн анализа эмиссионных документов.

        Порядок шагов пайплайна (строгий, не изменять):
          1. company_id — получение ID компании из БД (emitent_edisclosure) или поиска по ИНН на e-disclosure.
          2. Скачивание файлов с e-disclosure: документы берутся из таблицы emission_documents
             (по ИНН и рег. номеру), скачиваются по file_url (ZIP-архивы), извлекаются
             в подпапку backend/app/data/{secid}.
          3. Конвертация PDF → Markdown и сохранение: скачанные PDF передаются в сервис конвертации,
             полученные Markdown-файлы сохраняются на диск.
          4. Поиск событий: только после завершения шагов 2 и 3 запускается алгоритм
             find_events_by_reg_number для поиска событий по регистрационному номеру облигации.
          5. LLM-анализ: события и Markdown-документы передаются в языковую модель.

        Args:
            inn: ИНН компании.
            date: Граничная дата в формате YYYY-MM-DD; включаются события строго раньше неё.
            regnumber: Регистрационный номер облигации (опционально).
            emitent_moex_id: Не используется (документы берутся из emission_documents).
            secid: Идентификатор облигации для подпапки данных.

        Returns:
            Валидированный GeminiBondAnalysisDTO или None при ошибке анализа.

        Raises:
            ValueError: Компания не найдена или не удалось получить ID.
        """
        bond_data_dir: Path = _DATA_DIR / (secid or "unknown")
        bond_data_dir.mkdir(parents=True, exist_ok=True)

        # --- Шаг 1: company_id — из БД (emitent_edisclosure) или поиск по ИНН на e-disclosure ---
        company_id, companies = self._resolve_company_id_by_inn(inn)

        # --- Шаг 2: скачивание файлов с e-disclosure (emission_documents по ИНН и рег.номеру → ZIP → PDF) ---
        doc_filenames: List[str] = []
        if regnumber and regnumber.strip():
            emission_records: List[Dict[str, Any]] = (
                self._emission_doc_repo.get_by_inn_and_reg_number(inn, regnumber)
            )
            logger.info(
                "[E-DISCLOSURE DOCS] По ИНН и рег.номеру найдено записей в emission_documents: %d",
                len(emission_records),
            )
            for rec in emission_records:
                file_url: Optional[str] = rec.get("file_url")
                if not file_url or not str(file_url).strip():
                    continue
                content: Optional[bytes] = download_emission_file(file_url)
                if not content:
                    continue
                extracted: List[str] = extract_zip_to_dir(content, bond_data_dir)
                for name in extracted:
                    if name not in doc_filenames:
                        doc_filenames.append(name)
                if extracted:
                    print(
                        f"[E-DISCLOSURE DOCS] Из архива извлечено PDF: {extracted}",
                        flush=True,
                    )
            logger.info(
                "[E-DISCLOSURE DOCS] Итого PDF для конвертации: %d → %s",
                len(doc_filenames), doc_filenames,
            )
            if doc_filenames and not self._all_extracted_files_are_convertible(doc_filenames):
                _allowed: frozenset = frozenset({".pdf", ".docx", ".doc", ".rtf"})
                non_convertible: List[str] = [
                    f for f in doc_filenames if Path(f).suffix.lower() not in _allowed
                ]
                raise SkipBondException(
                    f"В архиве есть файлы, которые не входят в список допустимых "
                    f"(PDF, DOC, DOCX, RTF): {non_convertible}"
                )
        else:
            logger.info("[E-DISCLOSURE DOCS] Пропуск: рег.номер не задан")

        # --- Шаг 3: конвертация PDF → Markdown и сохранение (выполняется после полного скачивания, шаг 2) ---
        result: Dict[str, Any] = {
            "companies": companies,
            "events": [],
            "regnumber": regnumber,
            "search_date": date,
            "doc_filenames": doc_filenames,
            "data_dir": bond_data_dir,
        }
        if doc_filenames:
            logger.info(
                "[PDF2MD] → POST %s/api/v1/convert | PDF-файлов: %d → %s",
                settings.PDF2MD_BASE_URL,
                len(doc_filenames), doc_filenames,
            )
        converted: Dict[str, Any] = get_pdf_conversion_service().convert(result)
        converted["fallback_inn"] = inn
        md_filenames: List[str] = converted.get("md_filenames", [])
        logger.info(
            "[PDF2MD] Создано Markdown-файлов: %d → %s",
            len(md_filenames), md_filenames,
        )
        for md_name in md_filenames:
            print(f"[PDF2MD] Создан Markdown: {md_name}", flush=True)

        # Берём в рассмотрение только файлы с заголовком «РЕШЕНИЕ О ВЫПУСКЕ ЦЕННЫХ БУМАГ»; серию ищем только в разделе 1
        series: Optional[str] = None
        for md_name in md_filenames:
            try:
                md_path: Path = bond_data_dir / md_name
                md_content: str = self._file_storage.read_text_file(md_path)
                if not markdown_has_decision_header(md_content):
                    logger.info("[SERIES] Файл %s: заголовок «РЕШЕНИЕ О ВЫПУСКЕ ЦЕННЫХ БУМАГ» не найден — пропуск", md_name)
                    continue
                series = extract_series_from_markdown(md_content)
                if series is not None:
                    logger.info("[SERIES] Серия извлечена из %s: %s", md_name, series)
                    break
            except OSError as exc:
                logger.warning(
                    "[PDF2MD] Не удалось прочитать Markdown-файл %s: %s", md_path, exc
                )
        if series is None:
            logger.info("[SERIES] Серия не найдена (нет файла с заголовком и разделом 1 или паттерн «серии» не найден)")

        # --- Шаг 4: поиск событий (только после шагов 2 и 3), отбор по secid/рег.номер/серия в 2.1+2.3 ---
        logger.info(
            "[E-DISCLOSURE EVENTS] → GET https://www.e-disclosure.ru/api/events/page"
            " | company_id=%s, рег.номер=%s, граничная дата=%s",
            company_id, regnumber, date,
        )
        all_events: List[Dict[str, Any]] = get_events_with_full_text(
            date=date,
            company_id=company_id,
        )
        events: List[Dict[str, Any]] = filter_events_by_secid_regnumber_series(
            all_events, secid or "", regnumber or "", series
        )
        logger.info(
            "[E-DISCLOSURE EVENTS] По условиям secid/рег.номер/серия отобрано событий: %d",
            len(events),
        )

        # Выделение нужной текстовой части каждого события (удаление блоков по regex) перед сохранением
        for e in events:
            full: str = e.get("full_text", "")
            e["text"] = clean_event_text(full)

        # В events.json — полный текст и обработанный (с удалёнными частями по regex); в LLM — только обработанный
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
        logger.info("[E-DISCLOSURE EVENTS] Сохранён файл событий: %s", events_file)
        events_for_llm: List[Dict[str, Any]] = [
            {"event_name": e.get("event_name"), "event_date": e.get("event_date"), "text": e.get("text", "")}
            for e in events
        ]
        converted["events"] = events_for_llm
        converted["use_file_upload"] = use_file_upload

        # --- Шаг 5: анализ через LLM (с повтором при 503 UNAVAILABLE) ---
        logger.info("[LLM] Передача данных на анализ (провайдер: %s)...", provider)
        return self._call_llm_with_retry(converted, provider)

    # ------------------------------------------------------------------
    # Пакетная обработка всех флоатеров
    # ------------------------------------------------------------------

    def update_all_floaters(
        self,
        provider: Optional[str] = None,
        limit: Optional[int] = None,
        use_file_upload: bool = False,
        rating: Optional[str] = None,
    ) -> None:
        """Обрабатывает облигации вида «флоатер» (bond_kind=8), ещё не сохранённые.

        Получает полный список secid флоатеров, фильтрует уже обработанные
        (существующие в bond_float_params), затем для каждого оставшегося
        выполняет полный пайплайн: поиск компании, поиск событий, скачивание
        документов, конвертация PDF→MD, анализ LLM.
        Ограничение: не более 7 запросов к LLM в минуту.

        Args:
            provider: Имя LLM-провайдера. None или пустая строка — режим AUTO (проба удалённых).
            limit: Максимальное количество облигаций для обработки. None — все без данных.
            use_file_upload: Если True — для Gemini/OpenAI подавать в модель оригинальные
                файлы (PDF, Word) через Files API; иначе — только Markdown в промпте.
            rating: Если указан — обрабатываются только флоатеры с данным рейтингом.
                None — обрабатываются все флоатеры.

        Результаты записываются в БД (upsert — добавление или обновление полей).
        """
        resolved_provider: str = self._readiness.resolve_provider(provider)

        fl_logger: logging.Logger = _get_floaters_pipeline_logger()

        all_secids: List[str] = get_floater_secids(rating=rating)
        total_all: int = len(all_secids)

        existing_bond_ids: Set[int] = self._float_params_repo.get_existing_bond_ids()

        secids: List[str] = []
        skipped: int = 0
        for sid in all_secids:
            bid: Optional[int] = get_bond_id_by_secid(sid)
            if bid is not None and bid in existing_bond_ids:
                skipped += 1
                continue
            secids.append(sid)

        if limit is not None:
            secids = secids[:limit]

        total: int = len(secids)

        print(
            f"[ФЛОАТЕРЫ] Пайплайн обновления запущен. "
            f"Всего флоатеров: {total_all}, уже в БД: {skipped}, к обработке: {total}",
            flush=True,
        )

        fl_logger.info("=" * 60)
        fl_logger.info(
            "[FLOATERS PIPELINE START] Всего флоатеров: %d, уже в БД: %d, к обработке: %d",
            total_all, skipped, total,
        )
        logger.info(
            "[FLOATERS PIPELINE START] Всего флоатеров: %d, уже в БД: %d, к обработке: %d",
            total_all, skipped, total,
        )

        processed: int = 0
        saved: int = 0
        not_found_secids: List[str] = []
        quota_exhausted_error: Optional[GeminiQuotaExhaustedError] = None

        for secid in secids:
            processed += 1
            fl_logger.info(
                "[%d/%d] Обработка secid=%s", processed, total, secid
            )
            try:
                success: bool = self._process_single_floater(
                    secid,
                    fl_logger,
                    provider=resolved_provider,
                    use_file_upload=use_file_upload,
                )
                if success:
                    saved += 1
                    print(f"[ФЛОАТЕРЫ] {processed}/{total} — {secid}: данные сохранены", flush=True)
                else:
                    not_found_secids.append(secid)
                    print(f"[ФЛОАТЕРЫ] {processed}/{total} — {secid}: данные не найдены", flush=True)
            except GeminiQuotaExhaustedError as exc:
                quota_exhausted_error = exc
                fl_logger.error(
                    "[QUOTA EXHAUSTED] Исчерпана квота Gemini API (429). "
                    "Пайплайн остановлен, secid=%s: %s",
                    secid, exc,
                    exc_info=True,
                )
                print(
                    "[ФЛОАТЕРЫ] Остановка пайплайна: исчерпана квота Gemini API (429 RESOURCE_EXHAUSTED). "
                    "Процесс анализа завершён.",
                    flush=True,
                )
                break
            except GeminiUnavailableError as exc:
                fl_logger.error(
                    "[UNAVAILABLE] Gemini API 503 после повторов. Пайплайн остановлен, secid=%s: %s",
                    secid, exc,
                    exc_info=True,
                )
                print(
                    "[ФЛОАТЕРЫ] Остановка пайплайна: Gemini API 503 UNAVAILABLE после 3 попыток.",
                    flush=True,
                )
                raise
            except PdfConversionConnectionError as exc:
                fl_logger.error(
                    "[PDF2MD CONNECTION ERROR] Пайплайн остановлен, secid=%s: %s",
                    secid, exc,
                    exc_info=True,
                )
                logger.error(
                    "[PDF2MD CONNECTION ERROR] Пайплайн остановлен, secid=%s: %s",
                    secid, exc,
                    exc_info=True,
                )
                print(
                    f"[ФЛОАТЕРЫ] Остановка пайплайна: ошибка подключения к pdf2md — {exc}",
                    flush=True,
                )
                raise
            except Exception as exc:
                fl_logger.error(
                    "[ERROR] secid=%s: необработанная ошибка: %s", secid, exc, exc_info=True
                )
                not_found_secids.append(secid)
                print(f"[ФЛОАТЕРЫ] {processed}/{total} — {secid}: ошибка ({exc})", flush=True)

        summary: str = (
            f"[FLOATERS PIPELINE DONE] "
            f"Обработано: {processed}, "
            f"записей внесено: {saved}, "
            f"данные не найдены: {len(not_found_secids)}"
        )
        print(
            f"[ФЛОАТЕРЫ] Готово. Обработано: {processed}, "
            f"сохранено: {saved}, "
            f"не найдено: {len(not_found_secids)}",
            flush=True,
        )
        fl_logger.info(summary)
        logger.info(summary)

        if not_found_secids:
            secid_list_str: str = ", ".join(not_found_secids)
            fl_logger.info(
                "[NOT FOUND SECIDS] %s", secid_list_str
            )
            logger.info(
                "[NOT FOUND SECIDS] %s", secid_list_str
            )

        fl_logger.info("=" * 60)

        if quota_exhausted_error is not None:
            raise quota_exhausted_error

    def populate_emitent_edisclosure(self) -> Dict[str, int]:
        """Заполняет таблицу emitent_edisclosure по ИНН эмитентов.

        Для каждого эмитента с непустым ИНН, ещё не попавшего в таблицу,
        вызывает поиск компании на e-disclosure.ru (search_company_by_inn)
        и сохраняет соответствие через EmitentEdisclosureRepository.
        Обращение к БД — только через репозитории.

        Returns:
            Словарь: total_emitents, already_in_table, to_process, saved, skipped.
        """
        _delay: float = 2.0

        emitents: List[Dict[str, Any]] = self._emitents_repo.get_emitents_with_inn()
        existing_ids: Set[int] = self._emitent_edisclosure_repo.get_existing_emitent_ids()

        to_process: List[Dict[str, Any]] = [
            e for e in emitents if e["id"] not in existing_ids
        ]
        total: int = len(to_process)

        logger.info(
            "[emitent_edisclosure] Всего эмитентов с ИНН: %d, уже в таблице: %d, к обработке: %d",
            len(emitents), len(existing_ids), total,
        )

        saved: int = 0
        skipped: int = 0

        for idx, emitent in enumerate(to_process, start=1):
            emitent_id: int = emitent["id"]
            inn: str = emitent["inn"]

            try:
                companies: List[Dict[str, Any]] = search_company_by_inn(inn)
            except Exception as exc:
                logger.warning(
                    "[emitent_edisclosure] emitent_id=%s, ИНН=%s: ошибка запроса: %s",
                    emitent_id, inn, exc,
                )
                skipped += 1
                time.sleep(_delay)
                continue

            if not companies:
                logger.debug(
                    "[emitent_edisclosure] emitent_id=%s, ИНН=%s: компания не найдена",
                    emitent_id, inn,
                )
                skipped += 1
                time.sleep(_delay)
                continue

            raw_id: Optional[Any] = companies[0].get("id")
            if raw_id is None:
                logger.warning(
                    "[emitent_edisclosure] emitent_id=%s: id отсутствует в ответе",
                    emitent_id,
                )
                skipped += 1
                time.sleep(_delay)
                continue

            try:
                edisclosure_id: int = int(raw_id)
            except (TypeError, ValueError):
                logger.warning(
                    "[emitent_edisclosure] emitent_id=%s: невалидный id=%r",
                    emitent_id, raw_id,
                )
                skipped += 1
                time.sleep(_delay)
                continue

            try:
                self._emitent_edisclosure_repo.upsert_mapping(emitent_id, edisclosure_id)
                saved += 1
                logger.info(
                    "[emitent_edisclosure] %d/%d emitent_id=%s → edisclosure_id=%s",
                    idx, total, emitent_id, edisclosure_id,
                )
            except Exception as exc:
                logger.warning(
                    "[emitent_edisclosure] emitent_id=%s: ошибка записи: %s",
                    emitent_id, exc,
                )
                skipped += 1

            time.sleep(_delay)

        logger.info(
            "[emitent_edisclosure] Готово. Сохранено: %d, пропущено: %d",
            saved, skipped,
        )

        return {
            "total_emitents": len(emitents),
            "already_in_table": len(existing_ids),
            "to_process": total,
            "saved": saved,
            "skipped": skipped,
        }

    def fetch_emission_documents(
        self, limit: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Скачивает и сохраняет эмиссионные документы для эмитентов e-disclosure.

        Для каждого эмитента из таблицы emitent_edisclosure:
        1. Загружает HTML-страницу эмиссионных документов.
        2. Парсит таблицу документов.
        3. Если записей нет — логирует предупреждение со ссылкой на страницу.
        4. Иначе сохраняет записи через репозиторий.

        Приоритет обработки: сначала эмитенты без записей в emission_documents.

        Args:
            limit: Максимальное количество эмитентов для обработки. None — все.

        Returns:
            Статистика: processed, total_docs_added, empty_count.
        """
        _delay: float = 1.5

        emitents: List[Dict[str, Any]] = (
            self._emitent_edisclosure_repo.get_emitents_ordered_by_missing_docs(limit)
        )
        total: int = len(emitents)

        logger.info(
            "[emission_documents] Начало скачивания. Эмитентов к обработке: %d (limit=%s)",
            total, limit,
        )
        print(
            f"[emission_documents] Эмитентов к обработке: {total}",
            flush=True,
        )

        processed: int = 0
        total_docs_added: int = 0
        empty_count: int = 0

        for idx, emitent in enumerate(emitents, start=1):
            emitent_edisclosure_id: int = emitent["id"]
            edisclosure_id: int = emitent["edisclosure_id"]
            page_url: str = (
                f"https://www.e-disclosure.ru/portal/files.aspx"
                f"?id={edisclosure_id}&type=7"
            )

            try:
                html: str = fetch_emission_documents_page(edisclosure_id)
            except Exception as exc:
                logger.warning(
                    "[emission_documents] %d/%d emitent_edisclosure_id=%d: "
                    "ошибка загрузки страницы: %s. Ссылка: %s",
                    idx, total, emitent_edisclosure_id, exc, page_url,
                )
                processed += 1
                empty_count += 1
                time.sleep(_delay)
                continue

            docs: List[Dict[str, Optional[str]]] = parse_emission_documents(html)

            if not docs:
                logger.warning(
                    "[emission_documents] %d/%d emitent_edisclosure_id=%d "
                    "(edisclosure_id=%d): записей не найдено. Ссылка: %s",
                    idx, total, emitent_edisclosure_id, edisclosure_id, page_url,
                )
                print(
                    f"  [emission_documents] {idx}/{total} — "
                    f"edisclosure_id={edisclosure_id}: "
                    f"записей не найдено. {page_url}",
                    flush=True,
                )
                empty_count += 1
            else:
                inserted: int = self._emission_doc_repo.insert_batch(
                    emitent_edisclosure_id, docs,
                )
                total_docs_added += inserted
                logger.info(
                    "[emission_documents] %d/%d emitent_edisclosure_id=%d: "
                    "добавлено %d документов",
                    idx, total, emitent_edisclosure_id, inserted,
                )
                print(
                    f"  [emission_documents] {idx}/{total} — "
                    f"edisclosure_id={edisclosure_id}: "
                    f"добавлено {inserted} документов",
                    flush=True,
                )

            processed += 1
            time.sleep(_delay)

        summary: str = (
            f"[emission_documents] Готово. "
            f"Обработано: {processed}, "
            f"документов добавлено: {total_docs_added}, "
            f"без записей: {empty_count}"
        )
        logger.info(summary)
        print(summary, flush=True)

        return {
            "processed": processed,
            "total_docs_added": total_docs_added,
            "empty_count": empty_count,
        }

    def fetch_and_save_emitent_events_by_inn(
        self, inn: str, *, refresh_old: bool = False,
    ) -> Dict[str, Any]:
        """Пайплайн: ИНН → company_id → годы → события по годам в один JSON (без фильтров по заголовку).

        Файл: ``EMITENT_EVENTS_JSON_DIR / {inn}.json`` — ключи — строки годов, значения — списки
        ``event_name``, ``event_date``, ``full_text``, ``pseudoGUID``,
        ``is_corrected_by_another_event``, ``file_icon_name``.

        Если ``refresh_old=True`` — обновляет существующий файл: для каждого года
        обращается на API, сопоставляет старые события (без pseudoGUID) с серверными и
        дописывает недостающие ключи или перекачивает неоднозначные события.

        Если файл для данного ИНН **уже есть** (непустой JSON): считаем, что прошлые годы уже
        скачаны; запрашиваем ``EventsYears`` не нужно; проверяем и при необходимости догружаем
        **только текущий календарный год** — сравнение ``already_synced`` и список для загрузки
        строятся **только по событиям за этот год** в файле и на сервере. Для догрузки в пределах
        года берутся только события **позже** последней даты в файле за этот год (если она есть).

        Если файла нет, он пустой или не прочитан — **полная выгрузка** всех годов через
        ``list_company_portal_event_years``.
        """
        inn_clean: str = inn.strip()
        if not re.fullmatch(r"\d{10}(?:\d{2})?", inn_clean):
            raise ValueError("Некорректный ИНН: ожидается 10 или 12 цифр.")

        company_id, _ = self._resolve_company_id_by_inn(inn_clean)

        today: date = date.today()
        calendar_year_today: int = today.year

        out_path: Path = EMITENT_EVENTS_JSON_DIR / f"{inn_clean}.json"
        EMITENT_EVENTS_JSON_DIR.mkdir(parents=True, exist_ok=True)

        # --- refresh_old: обновление старых файлов до нового формата ---
        if refresh_old and out_path.exists():
            refresh_result: Dict[str, Any] = self._refresh_old_events_file(
                inn_clean, company_id, out_path,
            )
            return refresh_result

        resume_mode: bool = False
        last_event_cutoff: Optional[date] = None
        last_event_guid_saved: Optional[str] = None
        years_payload: Dict[str, List[Dict[str, Optional[str]]]] = {}
        years_processed: List[int] = []

        file_exists_with_events: bool = False
        raw_file: Any = None
        if out_path.exists():
            try:
                raw_file = self._file_storage.read_json(out_path)
            except (OSError, ValueError) as exc:
                logger.warning(
                    "[EMITENT EVENTS] Не удалось прочитать %s: %s — полная выгрузка",
                    out_path, exc,
                )
                raw_file = None
            if isinstance(raw_file, dict) and raw_file:
                file_exists_with_events = True

        if file_exists_with_events:
            resume_mode = True
            years_payload = {
                str(yk): [dict(ev) for ev in evs]
                for yk, evs in raw_file.items()
                if isinstance(evs, list)
            }
            year_key: str = str(calendar_year_today)
            current_year_file_only: Dict[str, Any] = {
                year_key: years_payload.get(year_key, []),
            }
            parsed_last: Optional[Tuple[date, str, int]] = (
                parse_latest_event_from_emitent_file_payload(current_year_file_only)
            )
            if parsed_last is not None:
                last_event_cutoff, last_event_guid_saved, _ = parsed_last
                print(
                    f"[EMITENT EVENTS] Файл найден — сверка и догрузка только за {calendar_year_today}: "
                    f"последнее событие в файле за этот год: date={last_event_cutoff}, "
                    f"pseudoGUID={last_event_guid_saved!r}",
                    flush=True,
                )
            else:
                print(
                    f"[EMITENT EVENTS] Файл найден — за {calendar_year_today} в файле нет событий, "
                    f"будет загрузка текущего года",
                    flush=True,
                )

            years_processed = [calendar_year_today]
            print(
                "[EMITENT EVENTS] Режим с файлом: без запроса EventsYears; обрабатывается только "
                f"текущий год {calendar_year_today}",
                flush=True,
            )

            if parsed_last is not None:
                api_latest: Optional[Tuple[date, str]] = find_latest_event_metadata_across_years(
                    company_id,
                    [calendar_year_today],
                    not_after=today,
                )
                if (
                    api_latest is not None
                    and last_event_cutoff is not None
                    and last_event_guid_saved is not None
                    and str(last_event_guid_saved).strip() != ""
                    and api_latest[0] == last_event_cutoff
                    and api_latest[1] == last_event_guid_saved
                ):
                    print(
                        "[EMITENT EVENTS] За текущий год: последнее событие в файле совпадает с "
                        "последним на портале (дата и pseudoGUID) — догрузка не требуется",
                        flush=True,
                    )
                    return {
                        "status": "ok",
                        "skipped": True,
                        "reason": "already_synced",
                        "inn": inn_clean,
                        "company_id": company_id,
                        "resume_mode": True,
                        "last_event_date": last_event_cutoff.isoformat(),
                        "last_event_pseudoGUID": last_event_guid_saved,
                        "file_path": str(out_path),
                        "current_year": calendar_year_today,
                        "calendar_year_today": calendar_year_today,
                        "years_processed": years_processed,
                        "counts_by_year": {
                            yk: len(v) for yk, v in years_payload.items()
                        },
                    }
        else:
            years_from_portal: List[int] = list_company_portal_event_years(company_id)
            years_processed = sorted(set(years_from_portal + [calendar_year_today]))
            if calendar_year_today not in years_from_portal:
                print(
                    f"[EMITENT EVENTS] Текущий календарный год {calendar_year_today} отсутствовал "
                    f"в EventsYears — добавлен в список загрузки",
                    flush=True,
                )
            print("[EMITENT EVENTS] Полная выгрузка (список годов с портала EventsYears)", flush=True)
            years_payload = {}

        if years_processed:
            period_lo: int = min(years_processed)
            period_hi: int = max(years_processed)
            print(
                f"[EMITENT EVENTS] Период загрузки: {period_lo}-{period_hi} "
                f"(years_count={len(years_processed)})",
                flush=True,
            )
        else:
            print("[EMITENT EVENTS] Список годов пуст — события не загружаются", flush=True)
        print(
            f"[EMITENT EVENTS] Годы для загрузки: {years_processed}",
            flush=True,
        )

        counts_by_year: Dict[str, int] = {}

        for y in years_processed:
            if y < calendar_year_today:
                boundary: str = f"{y + 1}-01-01"
            elif y == calendar_year_today:
                boundary = (today + timedelta(days=1)).isoformat()
            else:
                boundary = f"{y + 1}-01-01"
            print(
                f"[EMITENT EVENTS] Загружается год={y}, boundary_date={boundary}",
                flush=True,
            )
            year_events: List[Dict[str, Optional[str]]] = fetch_emitent_year_events_unfiltered(
                company_id=company_id,
                api_year=y,
                boundary_date=boundary,
            )
            if (
                resume_mode
                and last_event_cutoff is not None
                and y == calendar_year_today
            ):
                filtered: List[Dict[str, Optional[str]]] = []
                for ev in year_events:
                    ds: Optional[str] = ev.get("event_date")
                    if not ds:
                        continue
                    try:
                        ed: date = datetime.strptime(str(ds)[:10], "%Y-%m-%d").date()
                    except ValueError:
                        continue
                    if ed > last_event_cutoff:
                        filtered.append(ev)
                year_events = filtered
                print(
                    f"[EMITENT EVENTS] После отсечения по дате > {last_event_cutoff} "
                    f"(текущий год): {len(year_events)} событий",
                    flush=True,
                )

            key: str = str(y)
            if resume_mode:
                prev: List[Dict[str, Optional[str]]] = years_payload.get(key, [])
                years_payload[key] = merge_emitent_event_lists(prev, year_events)
            else:
                years_payload[key] = year_events
            counts_by_year[key] = len(years_payload[key])

        self._file_storage.write_json(out_path, years_payload)

        start_year: Optional[int] = min(years_processed) if years_processed else None
        end_year: Optional[int] = max(years_processed) if years_processed else None

        return {
            "status": "ok",
            "skipped": False,
            "inn": inn_clean,
            "company_id": company_id,
            "resume_mode": resume_mode,
            "start_year": start_year,
            "end_year": end_year,
            "current_year": calendar_year_today,
            "calendar_year_today": calendar_year_today,
            "years_processed": years_processed,
            "counts_by_year": counts_by_year,
            "file_path": str(out_path),
            "last_event_date_in_file": last_event_cutoff.isoformat()
            if resume_mode and last_event_cutoff is not None
            else None,
        }

    def _refresh_old_events_file(
        self,
        inn: str,
        company_id: int,
        out_path: Path,
    ) -> Dict[str, Any]:
        """Обновляет существующий JSON-файл событий до нового формата (с pseudoGUID и др.).

        Для каждого года в файле:
        1. Запрашивает с сервера список событий за этот год (без полных текстов).
        2. Для каждого события в файле ищет соответствие на сервере по (event_date, event_name).
        3. Если ровно одно совпадение — дописывает ключи pseudoGUID,
           is_corrected_by_another_event, file_icon_name.
        4. Если несколько совпадений (одна дата + одинаковый заголовок) — удаляет все
           такие события из файла и скачивает их с сервера заново (с полным текстом).

        Args:
            inn: ИНН эмитента.
            company_id: ID компании на e-disclosure.ru.
            out_path: Путь к файлу {inn}.json.

        Returns:
            Сводка обновления.
        """
        from app.utils.edisclosure_utils import (
            _fetch_emitent_event_text_worker,
            _find_all_events_sorted_by_date_include_all,
            _format_event_date,
        )

        try:
            raw_file: Any = self._file_storage.read_json(out_path)
        except (OSError, ValueError) as exc:
            logger.warning(
                "[REFRESH OLD] Не удалось прочитать %s: %s", out_path, exc,
            )
            return {"status": "error", "detail": f"Не удалось прочитать файл: {exc}"}

        if not isinstance(raw_file, dict) or not raw_file:
            return {"status": "error", "detail": "Файл пуст или имеет неверный формат"}

        years_payload: Dict[str, List[Dict[str, Any]]] = {
            str(yk): [dict(ev) for ev in evs]
            for yk, evs in raw_file.items()
            if isinstance(evs, list)
        }

        total_enriched: int = 0
        total_redownloaded: int = 0
        years_touched: List[str] = []

        for year_key in sorted(years_payload.keys()):
            file_events: List[Dict[str, Any]] = years_payload[year_key]
            # Пропускаем годы, в которых все события уже содержат pseudoGUID
            if all(ev.get("pseudoGUID") for ev in file_events):
                continue

            try:
                api_year: int = int(year_key)
            except ValueError:
                continue

            years_touched.append(year_key)
            print(
                f"[REFRESH OLD] Обработка года {year_key}: "
                f"{len(file_events)} событий в файле",
                flush=True,
            )

            # Загружаем метаданные событий с сервера (без полных текстов)
            api_events: List[Dict[str, Any]] = fetch_events_page_json_only(
                company_id, api_year,
            )

            # Индексируем серверные события по (event_date_str, event_name)
            api_index: Dict[Tuple[str, str], List[Dict[str, Any]]] = {}
            for api_ev in api_events:
                api_date_str: Optional[str] = _format_event_date(api_ev.get("eventDate"))
                api_name: str = (api_ev.get("eventName") or "").strip()
                if api_date_str:
                    idx_key: Tuple[str, str] = (api_date_str, api_name)
                    api_index.setdefault(idx_key, []).append(api_ev)

            updated_events: List[Dict[str, Any]] = []
            ambiguous_keys: set = set()

            for ev in file_events:
                if ev.get("pseudoGUID"):
                    # Уже содержит pseudoGUID — оставляем как есть
                    updated_events.append(ev)
                    continue

                ev_date: str = str(ev.get("event_date") or "")
                ev_name: str = str(ev.get("event_name") or "")
                match_key: Tuple[str, str] = (ev_date, ev_name)
                matches: List[Dict[str, Any]] = api_index.get(match_key, [])

                if len(matches) == 1:
                    # Ровно одно совпадение — дописываем ключи
                    api_match: Dict[str, Any] = matches[0]
                    ev["pseudoGUID"] = str(api_match.get("pseudoGUID") or "")
                    ev["is_corrected_by_another_event"] = bool(
                        api_match.get("isCorrectedByAnotherEvent")
                    )
                    ev["file_icon_name"] = (
                        str(api_match.get("fileIconName"))
                        if api_match.get("fileIconName")
                        else None
                    )
                    updated_events.append(ev)
                    total_enriched += 1
                elif len(matches) > 1:
                    # Несколько совпадений — помечаем для перекачки
                    ambiguous_keys.add(match_key)
                else:
                    # Нет совпадений на сервере — оставляем как есть
                    updated_events.append(ev)

            # Перекачиваем неоднозначные события (с полным текстом)
            if ambiguous_keys:
                # Удаляем из updated_events все события с такими ключами
                # (они могли быть добавлены из предыдущих итераций с pseudoGUID)
                updated_events = [
                    ev for ev in updated_events
                    if (
                        str(ev.get("event_date") or ""),
                        str(ev.get("event_name") or ""),
                    ) not in ambiguous_keys
                ]
                for amb_key in ambiguous_keys:
                    api_matches: List[Dict[str, Any]] = api_index[amb_key]
                    for api_ev in api_matches:
                        pseudo_guid: str = str(api_ev.get("pseudoGUID") or "")
                        if not pseudo_guid:
                            continue
                        # Загружаем полный текст события
                        _, result_ev = _fetch_emitent_event_text_worker((
                            0,
                            pseudo_guid,
                            api_ev.get("eventDate"),
                            api_ev.get("eventName"),
                            pseudo_guid,
                            api_ev.get("isCorrectedByAnotherEvent"),
                            api_ev.get("fileIconName"),
                        ))
                        if result_ev is not None:
                            updated_events.append(result_ev)
                            total_redownloaded += 1

                print(
                    f"[REFRESH OLD] Год {year_key}: неоднозначных групп={len(ambiguous_keys)}, "
                    f"перекачано событий={total_redownloaded}",
                    flush=True,
                )

            years_payload[year_key] = updated_events

        self._file_storage.write_json(out_path, years_payload)

        summary_msg: str = (
            f"[REFRESH OLD] Готово. Обогащено: {total_enriched}, "
            f"перекачано: {total_redownloaded}, годов затронуто: {len(years_touched)}"
        )
        print(summary_msg, flush=True)
        logger.info(summary_msg)

        return {
            "status": "ok",
            "refresh_old": True,
            "inn": inn,
            "company_id": company_id,
            "file_path": str(out_path),
            "total_enriched": total_enriched,
            "total_redownloaded": total_redownloaded,
            "years_touched": years_touched,
        }

    def fetch_and_save_emitent_events_for_all_emitents(
        self, *, refresh_old: bool = False,
    ) -> Dict[str, Any]:
        """Пакетная выгрузка событий: для каждого уникального ИНН из таблицы emitents.

        Порядок ИНН — как в ответе репозитория; дубликаты ИНН (несколько строк эмитента)
        объединяются в один проход на ИНН. Сбой по одному ИНН не прерывает остальные.

        Args:
            refresh_old: Если True — для каждого ИНН выполняется обновление
                существующего файла до нового формата (с pseudoGUID и др.).

        Returns:
            Сводка: status, batch, total_emitents_rows, unique_inn_count, unique_inns,
            processed, succeeded, failed, results, errors.
        """
        emitents_rows: List[Dict[str, Any]] = self._emitents_repo.get_emitents_with_inn()
        total_emitents_rows: int = len(emitents_rows)

        seen_inns: Set[str] = set()
        unique_inns_ordered: List[str] = []
        for row in emitents_rows:
            inn_raw: Any = row.get("inn")
            inn_str: str = str(inn_raw).strip() if inn_raw is not None else ""
            if not inn_str:
                continue
            if inn_str in seen_inns:
                continue
            seen_inns.add(inn_str)
            unique_inns_ordered.append(inn_str)

        unique_inn_count: int = len(unique_inns_ordered)
        results: List[Dict[str, Any]] = []
        errors: List[Dict[str, str]] = []

        print(
            f"[EMITENT EVENTS BATCH] Старт пакета: уникальных эмитентов (ИНН) к обработке: "
            f"{unique_inn_count}",
            flush=True,
        )

        for num, inn_item in enumerate(unique_inns_ordered, start=1):
            try:
                one_result: Dict[str, Any] = self.fetch_and_save_emitent_events_by_inn(
                    inn_item, refresh_old=refresh_old,
                )
                results.append(one_result)
            except ValueError as exc:
                logger.warning(
                    "[EMITENT EVENTS BATCH] ИНН=%s: ValueError: %s",
                    inn_item, exc,
                )
                errors.append({"inn": inn_item, "detail": str(exc)})
            except Exception as exc:
                logger.error(
                    "[EMITENT EVENTS BATCH] ИНН=%s: ошибка: %s",
                    inn_item, exc,
                    exc_info=True,
                )
                errors.append({"inn": inn_item, "detail": str(exc)})
            print(
                f"[EMITENT EVENTS BATCH] Обработано эмитентов: {num} из {unique_inn_count} "
                f"(ИНН={inn_item})",
                flush=True,
            )

        processed: int = unique_inn_count
        succeeded: int = len(results)
        failed: int = len(errors)
        batch_ok: bool = unique_inn_count == 0 or succeeded > 0
        status: str = "ok" if batch_ok else "error"

        return {
            "status": status,
            "batch": True,
            "total_emitents_rows": total_emitents_rows,
            "unique_inn_count": unique_inn_count,
            "unique_inns": unique_inns_ordered,
            "processed": processed,
            "succeeded": succeeded,
            "failed": failed,
            "results": results,
            "errors": errors,
        }

    def _process_single_floater(
        self,
        secid: str,
        fl_logger: logging.Logger,
        provider: str = "gemini",
        use_file_upload: bool = False,
    ) -> bool:
        """Выполняет полный пайплайн анализа для одной облигации-флоатера.

        Порядок шагов пайплайна (строгий, не изменять):
          1. company_id — получение ID компании из БД (emitent_edisclosure) или поиска по ИНН на e-disclosure.
          2. Скачивание файлов с e-disclosure: документы берутся из emission_documents
             по ИНН и рег. номеру (ZIP по file_url, распаковка в папку по secid).
          3. Конвертация PDF → Markdown и сохранение: скачанные PDF передаются в сервис конвертации,
             полученные Markdown-файлы сохраняются на диск.
          4. Поиск событий: только после завершения шагов 2 и 3 запускается алгоритм
             find_events_by_reg_number для поиска событий по регистрационному номеру облигации.
          5. LLM-анализ: события и Markdown-документы передаются в языковую модель.

        Args:
            secid: Идентификатор ценной бумаги.
            fl_logger: Логгер пайплайна флоатеров.
            provider: Провайдер LLM («gemini» или «openai»).
            use_file_upload: Использовать ли File Upload API для передачи Markdown-файлов в LLM.

        Returns:
            True если данные успешно сохранены, False если данные не найдены.
        """
        print(f"  [{secid}] Старт пайплайна", flush=True)
        bond_data_dir: Path = _DATA_DIR / secid
        bond_data_dir.mkdir(parents=True, exist_ok=True)

        inn: Optional[str] = get_emitent_inn_by_secid(secid)
        if not inn:
            fl_logger.warning("[NOT FOUND] secid=%s: ИНН эмитента не найден", secid)
            bond_id: Optional[int] = get_bond_id_by_secid(secid)
            if bond_id is not None:
                self._float_params_repo.upsert_not_found(bond_id, _get_not_found_float_params_data())
            return False

        regnumber: Optional[str] = get_reg_number_by_secid(secid)
        emitent_moex_id: Optional[int] = get_emitent_moex_id_by_secid(secid)
        bond_id = get_bond_id_by_secid(secid)
        print(
            f"  [{secid}] Из БД: regnumber={repr(regnumber)}, emitent_moex_id={emitent_moex_id}",
            flush=True,
        )

        trading_service = get_trading_history_service()
        first_tradedate = trading_service.get_first_tradedate(secid)
        date_str: str = (
            first_tradedate.isoformat() if first_tradedate is not None else _DEFAULT_DATE
        )

        # --- Шаг 1: company_id — из БД (emitent_edisclosure) или поиск по ИНН на e-disclosure ---
        print(f"  [{secid}] Шаг 1/5: company_id (БД или e-disclosure, ИНН={inn})", flush=True)
        company_id: int
        companies: List[Dict[str, Any]]
        try:
            company_id, companies = self._resolve_company_id_by_inn(inn)
        except ValueError:
            fl_logger.warning(
                "[NOT FOUND] secid=%s: компания с ИНН=%s не найдена на e-disclosure",
                secid, inn,
            )
            if bond_id is not None:
                self._float_params_repo.upsert_not_found(
                    bond_id, _get_not_found_float_params_data()
                )
            return False
        except Exception as exc:
            fl_logger.warning(
                "[NOT FOUND] secid=%s: ошибка поиска компании: %s", secid, exc
            )
            if bond_id is not None:
                self._float_params_repo.upsert_not_found(
                    bond_id, _get_not_found_float_params_data()
                )
            return False

        # --- Шаг 2: скачивание файлов с e-disclosure (emission_documents по ИНН и рег.номеру → ZIP → PDF) ---
        print(f"  [{secid}] Шаг 2/5: скачивание файлов с e-disclosure (ИНН + рег.номер)", flush=True)
        doc_filenames_batch: List[str] = []
        if regnumber and regnumber.strip():
            try:
                emission_records_batch: List[Dict[str, Any]] = (
                    self._emission_doc_repo.get_by_inn_and_reg_number(inn, regnumber)
                )
                for rec in emission_records_batch:
                    file_url_batch: Optional[str] = rec.get("file_url")
                    if not file_url_batch or not str(file_url_batch).strip():
                        continue
                    content_batch: Optional[bytes] = download_emission_file(file_url_batch)
                    if not content_batch:
                        continue
                    extracted_batch: List[str] = extract_zip_to_dir(
                        content_batch, bond_data_dir
                    )
                    for name in extracted_batch:
                        if name not in doc_filenames_batch:
                            doc_filenames_batch.append(name)
                    if extracted_batch:
                        print(
                            f"  [E-DISCLOSURE DOCS] Из архива извлечено PDF: {extracted_batch}",
                            flush=True,
                        )
            except Exception as exc:
                fl_logger.warning(
                    "[NOT FOUND] secid=%s: ошибка скачивания документов: %s", secid, exc
                )

        if doc_filenames_batch and not self._all_extracted_files_are_convertible(
            doc_filenames_batch
        ):
            _allowed: frozenset = frozenset({".pdf", ".docx", ".doc", ".rtf"})
            non_convertible_batch: List[str] = [
                f for f in doc_filenames_batch if Path(f).suffix.lower() not in _allowed
            ]
            fl_logger.info(
                "[SKIP] secid=%s: в архиве есть файлы, которые не входят в список допустимых "
                "(PDF, DOC, DOCX, RTF): %s — обработка пропущена, в БД не записываем",
                secid, non_convertible_batch,
            )
            print(
                f"  [{secid}] Пропуск: в архиве файлы, не входящие в список допустимых "
                f"(PDF, DOC, DOCX, RTF) — {non_convertible_batch}",
                flush=True,
            )
            return False

        # --- Шаг 3: конвертация PDF → Markdown и сохранение (выполняется после полного скачивания, шаг 2) ---
        print(f"  [{secid}] Шаг 3/5: конвертация PDF → Markdown и сохранение", flush=True)
        result_dict: Dict[str, Any] = {
            "companies": companies,
            "events": [],
            "regnumber": regnumber,
            "search_date": date_str,
            "doc_filenames": doc_filenames_batch,
            "data_dir": bond_data_dir,
        }
        converted: Dict[str, Any] = get_pdf_conversion_service().convert(result_dict)
        converted["fallback_inn"] = inn
        md_filenames_batch: List[str] = converted.get("md_filenames", [])
        for md_name in md_filenames_batch:
            print(f"[PDF2MD] Создан Markdown: {md_name}", flush=True)

        # Берём в рассмотрение только файлы с заголовком «РЕШЕНИЕ О ВЫПУСКЕ ЦЕННЫХ БУМАГ»; серию ищем только в разделе 1
        series: Optional[str] = None
        for md_name in md_filenames_batch:
            try:
                md_path_batch: Path = bond_data_dir / md_name
                md_content_batch: str = self._file_storage.read_text_file(md_path_batch)
                if not markdown_has_decision_header(md_content_batch):
                    print(f"  [{secid}] Файл {md_name!r}: заголовок «РЕШЕНИЕ О ВЫПУСКЕ ЦЕННЫХ БУМАГ» не найден — пропуск", flush=True)
                    continue
                series = extract_series_from_markdown(md_content_batch)
                if series is not None:
                    print(f"  [{secid}] Серия извлечена из {md_name!r}: {series!r}", flush=True)
                    break
            except OSError as exc:
                fl_logger.warning(
                    "[PDF2MD] secid=%s: не удалось прочитать Markdown-файл %s: %s",
                    secid, md_path_batch, exc,
                )
        if series is None:
            print(f"  [{secid}] Серия не найдена (нет файла с заголовком и разделом 1 или паттерн «серии» не найден)", flush=True)

        # --- Шаг 4: поиск событий (только после шагов 2 и 3), отбор по secid/рег.номер/серия в 2.1+2.3 ---
        print(f"  [{secid}] Шаг 4/5: поиск событий по рег.номеру", flush=True)
        events: List[Dict[str, Any]] = []
        try:
            all_events_batch: List[Dict[str, Any]] = get_events_with_full_text(
                date=date_str,
                company_id=company_id,
            )
            events = filter_events_by_secid_regnumber_series(
                all_events_batch, secid or "", regnumber or "", series
            )
            print(
                f"  [{secid}] По условиям secid/рег.номер/серия отобрано событий: {len(events)}",
                flush=True,
            )
        except Exception as exc:
            fl_logger.warning(
                "[NOT FOUND] secid=%s: ошибка поиска событий: %s", secid, exc
            )

        # Выделение нужной текстовой части каждого события (удаление блоков по regex) перед сохранением
        for e in events:
            full_batch: str = e.get("full_text", "")
            e["text"] = clean_event_text(full_batch)

        # В events.json — полный текст и обработанный (с удалёнными частями по regex); в LLM — только обработанный
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
        converted["events"] = events_for_llm_batch
        converted["use_file_upload"] = use_file_upload

        if not events and not doc_filenames_batch:
            fl_logger.warning(
                "[NOT FOUND] secid=%s: не найдено ни событий (%d), ни документов (%d)",
                secid, len(events), len(doc_filenames_batch),
            )
            if bond_id is not None:
                self._float_params_repo.upsert_not_found(bond_id, _get_not_found_float_params_data())
            return False

        # --- Шаг 5: LLM-анализ с ограничением частоты и повтором при 503 UNAVAILABLE ---
        print(f"  [{secid}] Шаг 5/5: анализ LLM", flush=True)
        self._enforce_llm_rate_limit()
        analysis: Optional[GeminiBondAnalysisDTO] = self._call_llm_with_retry(converted, provider)

        if analysis is None:
            fl_logger.warning(
                "[NOT FOUND] secid=%s: LLM вернул невалидный ответ", secid
            )
            if bond_id is not None:
                self._float_params_repo.upsert_not_found(bond_id, _get_not_found_float_params_data())
            return False

        # --- Сохранение ---
        print(f"  [{secid}] Сохранение в БД", flush=True)
        if bond_id is not None:
            self._float_params_repo.upsert(bond_id, analysis)
            fl_logger.info("[SAVED] secid=%s, bond_id=%d", secid, bond_id)
        else:
            fl_logger.warning(
                "[NOT FOUND] secid=%s: bond_id не найден — запись пропущена", secid
            )
            return False

        return True

    def _enforce_llm_rate_limit(self) -> None:
        """Ограничивает частоту запросов к LLM: не более 7 вызовов за 60 секунд."""
        now: float = time.time()
        self._llm_call_timestamps = [
            t for t in self._llm_call_timestamps if now - t < 60.0
        ]
        if len(self._llm_call_timestamps) >= 7:
            oldest: float = self._llm_call_timestamps[0]
            sleep_seconds: float = 60.0 - (now - oldest) + 0.1
            if sleep_seconds > 0:
                logger.info(
                    "[RATE LIMIT] Достигнут лимит 7 запросов/мин, ожидание %.1f сек",
                    sleep_seconds,
                )
                time.sleep(sleep_seconds)
            now = time.time()
            self._llm_call_timestamps = [
                t for t in self._llm_call_timestamps if now - t < 60.0
            ]
        self._llm_call_timestamps.append(time.time())


_edisclosure_service: Optional[EdisclosureService] = None


def get_edisclosure_service() -> EdisclosureService:
    """Возвращает singleton EdisclosureService."""
    global _edisclosure_service
    if _edisclosure_service is None:
        _edisclosure_service = EdisclosureService()
    return _edisclosure_service
