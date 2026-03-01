"""Сервис для работы с e-disclosure.ru.

Содержит логику вызова методов из edisclosure_utils: получение company_id из БД
(emitent_edisclosure) или поиск компаний по ИНН на e-disclosure, поиск событий
по регистрационному номеру облигации и скачивание эмиссионных документов из
таблицы emission_documents (по ИНН и рег. номеру) с распаковкой ZIP в папку по secid.
Эндпоинт вызывает get_accrued_income_by_secid(secid), который после получения
результата анализа от Gemini сохраняет данные в БД через BondFloatParamsRepository
и удаляет временные файлы из _DATA_DIR.

Метод update_all_floaters() обрабатывает все облигации вида «флоатер» (bond_kind=8)
в пакетном режиме с ограничением на количество запросов к LLM (7 в минуту).
"""

import json
import logging
import time
from datetime import datetime
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
from app.repository.db.emission_document_repository import EmissionDocumentRepository
from app.utils.edisclosure_utils import (
    download_emission_file,
    extract_zip_to_dir,
    fetch_emission_documents_page,
    find_events_by_reg_number,
    search_company_by_inn,
)

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

    def _get_analysis_service(self, provider: str) -> Any:
        """Возвращает сервис LLM-анализа по имени провайдера.

        Args:
            provider: Имя провайдера ("gemini", "gemini-flash", "gemini-3-flash", "openai-gpt-5.1", "openrouter" или "local").
                gemini — Flash Lite, gemini-flash — 2.5 Flash, gemini-3-flash — 3 Flash, openai-gpt-5.1 — OpenAI GPT-5.1.

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
        if provider == "gemini-3-flash":
            return GEMINI_MODEL_3_FLASH
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

    def get_accrued_income_by_secid(self, secid: str, provider: str = "gemini") -> Dict[str, str]:
        """Получает данные флоатера по SECID, анализирует через Gemini и сохраняет в БД.

        1. Получает ИНН эмитента и рег. номер облигации по secid из БД.
        2. Получает наименьшую дату из таблицы истории торгов.
        3. Вызывает _get_accrued_income_by_inn для анализа через Gemini.
        4. Если Gemini вернул None (ошибка валидации) — пропускает запись в БД,
           очищает файлы и возвращает {"status": "error", "detail": "..."}.
        5. Сохраняет результат анализа в БД через BondFloatParamsRepository.
        6. Удаляет временные файлы .pdf и .md из _DATA_DIR.
        7. Возвращает {"status": "ok"}.

        Args:
            secid: Идентификатор ценной бумаги.

        Returns:
            Словарь {"status": "ok"} или {"status": "error", "detail": "..."}.

        Raises:
            ValueError: ИНН эмитента не найден в БД.
        """
        secid = (secid or "").strip()
        if not secid:
            raise ValueError("SECID не указан")

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

        analysis: Optional[GeminiBondAnalysisDTO] = self._get_accrued_income_by_inn(
            inn=inn,
            date=date_str,
            regnumber=regnumber,
            emitent_moex_id=emitent_moex_id,
            provider=provider,
            secid=secid,
        )

        if analysis is None:
            logger.warning(
                "[PIPELINE] Анализ Gemini вернул None — запись в БД пропущена. secid=%s",
                secid,
            )
            self._cleanup_data_files()
            return {"status": "error", "detail": "Ошибка валидации ответа LLM"}

        bond_id: Optional[int] = get_bond_id_by_secid(secid)
        if bond_id is not None:
            logger.info("[DB SAVE] Сохранение параметров флоатера: bond_id=%d", bond_id)
            self._float_params_repo.upsert(bond_id, analysis)
            logger.info("[DB SAVE] Успешно сохранено: bond_id=%d", bond_id)
        else:
            logger.warning("[DB SAVE] bond_id не найден для secid=%s — запись пропущена", secid)

        self._cleanup_data_files()
        logger.info("[PIPELINE DONE] secid=%s → статус: ok", secid)
        logger.info("=" * 60)
        return {"status": "ok"}

    def _cleanup_data_files(self) -> None:
        """Удаляет все файлы .pdf и .md из директории данных после успешного сохранения.

        Делегирует файловую операцию в FileStorage (repository/files) согласно
        принципу разделения ответственности по слоям архитектуры.
        """
        # self._file_storage.delete_files_by_pattern(
        #     directory=_DATA_DIR,
        #     extensions=("*.pdf", "*.md"),
        # )
        pass

    def _get_accrued_income_by_inn(
        self,
        inn: str,
        date: str = "2025-04-24",
        regnumber: Optional[str] = None,
        emitent_moex_id: Optional[int] = None,
        provider: str = "gemini",
        secid: str = "",
    ) -> Optional[GeminiBondAnalysisDTO]:
        """Получает данные компании по ИНН, скачивает документы и анализирует их через Gemini.

        Вызывает search_company_by_inn для получения ID компании, затем
        find_events_by_reg_number для поиска всех событий года, в которых
        присутствует регистрационный номер облигации или его части.
        Если regnumber не задан — возвращает пустой список событий.
        Документы берутся из таблицы emission_documents (по ИНН и рег. номеру),
        скачиваются по file_url (ZIP-архивы), извлекаются в подпапку backend/app/data/{secid},
        конвертируются в Markdown и передаются в GeminiAnalysisService.

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
        emitent_id: Optional[int] = self._emitents_repo.get_emitent_id_by_inn(inn)
        edisclosure_id: Optional[int] = None
        if emitent_id is not None:
            edisclosure_id = self._emitent_edisclosure_repo.get_edisclosure_id_by_emitent_id(
                emitent_id
            )
        company_id: Any
        if edisclosure_id is not None:
            company_id = edisclosure_id
            companies = [{"id": company_id, "name": ""}]
            logger.info(
                "[E-DISCLOSURE] company_id=%s взят из таблицы emitent_edisclosure (ИНН=%s)",
                company_id, inn,
            )
        else:
            logger.info(
                "[E-DISCLOSURE] → POST https://www.e-disclosure.ru/api/search/companies | ИНН=%s",
                inn,
            )
            companies = search_company_by_inn(inn)
            if not companies:
                raise ValueError(f"Компания с ИНН {inn} не найдена на e-disclosure.ru")
            company_id = companies[0].get("id")
            if company_id is None:
                raise ValueError("Не удалось получить ID компании из ответа e-disclosure")
            logger.info(
                "[E-DISCLOSURE] Найдено компаний: %d, company_id=%s, название=%s",
                len(companies), company_id, companies[0].get("name"),
            )

        # --- Шаг 2: скачивание эмиссионных документов из БД (emission_documents) по ИНН и рег.номеру ---
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
        else:
            logger.info("[E-DISCLOSURE DOCS] Пропуск: рег.номер не задан")

        # --- Шаг 3: конвертация PDF → Markdown ---
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
                "http://localhost:9000",
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

        # --- Шаг 4: поиск событий по регистрационному номеру ---
        if not regnumber or not regnumber.strip():
            events: List[Dict[str, Any]] = []
            logger.info("[E-DISCLOSURE EVENTS] рег.номер не задан — события пропущены")
        else:
            logger.info(
                "[E-DISCLOSURE EVENTS] → GET https://www.e-disclosure.ru/api/events/page"
                " | company_id=%s, рег.номер=%s, граничная дата=%s",
                company_id, regnumber, date,
            )
            events = find_events_by_reg_number(
                date=date,
                company_id=company_id,
                reg_number=regnumber,
            )
            logger.info(
                "[E-DISCLOSURE EVENTS] Найдено событий с упоминанием рег.номера: %d",
                len(events),
            )

        # В events.json — полный текст и обработанный (для отладки); в LLM — только обработанный
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

        # --- Шаг 5: анализ через LLM (с повтором при 503 UNAVAILABLE) ---
        logger.info("[LLM] Передача данных на анализ (провайдер: %s)...", provider)
        return self._call_llm_with_retry(converted, provider)

    # ------------------------------------------------------------------
    # Пакетная обработка всех флоатеров
    # ------------------------------------------------------------------

    def update_all_floaters(
        self, provider: str = "gemini", limit: Optional[int] = None
    ) -> None:
        """Обрабатывает облигации вида «флоатер» (bond_kind=8), ещё не сохранённые.

        Получает полный список secid флоатеров, фильтрует уже обработанные
        (существующие в bond_float_params), затем для каждого оставшегося
        выполняет полный пайплайн: поиск компании, поиск событий, скачивание
        документов, конвертация PDF→MD, анализ LLM.
        Ограничение: не более 7 запросов к LLM в минуту.

        Args:
            provider: Имя LLM-провайдера.
            limit: Максимальное количество облигаций для обработки. None — все без данных.

        Результаты записываются в БД (upsert — добавление или обновление полей).
        """
        fl_logger: logging.Logger = _get_floaters_pipeline_logger()

        all_secids: List[str] = get_floater_secids()
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
                success: bool = self._process_single_floater(secid, fl_logger, provider=provider)
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
            except Exception as exc:
                fl_logger.error(
                    "[ERROR] secid=%s: необработанная ошибка: %s", secid, exc, exc_info=True
                )
                not_found_secids.append(secid)
                print(f"[ФЛОАТЕРЫ] {processed}/{total} — {secid}: ошибка ({exc})", flush=True)
            finally:
                self._cleanup_data_files()

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

    def _process_single_floater(
        self, secid: str, fl_logger: logging.Logger, provider: str = "gemini",
    ) -> bool:
        """Выполняет полный пайплайн анализа для одной облигации-флоатера.

        regnumber получается из БД по secid. Документы скачиваются из emission_documents
        по ИНН и рег. номеру (ZIP по file_url, распаковка в папку по secid).

        Args:
            secid: Идентификатор ценной бумаги.
            fl_logger: Логгер пайплайна флоатеров.

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
        emitent_id_batch: Optional[int] = self._emitents_repo.get_emitent_id_by_inn(inn)
        edisclosure_id_batch: Optional[int] = None
        if emitent_id_batch is not None:
            edisclosure_id_batch = self._emitent_edisclosure_repo.get_edisclosure_id_by_emitent_id(
                emitent_id_batch
            )
        company_id: Any
        if edisclosure_id_batch is not None:
            company_id = edisclosure_id_batch
            companies = [{"id": company_id, "name": ""}]
        else:
            try:
                companies = search_company_by_inn(inn)
            except Exception as exc:
                fl_logger.warning(
                    "[NOT FOUND] secid=%s: ошибка поиска компании: %s", secid, exc
                )
                if bond_id is not None:
                    self._float_params_repo.upsert_not_found(
                        bond_id, _get_not_found_float_params_data()
                    )
                return False
            if not companies:
                fl_logger.warning(
                    "[NOT FOUND] secid=%s: компания с ИНН=%s не найдена на e-disclosure",
                    secid, inn,
                )
                if bond_id is not None:
                    self._float_params_repo.upsert_not_found(
                        bond_id, _get_not_found_float_params_data()
                    )
                return False
            company_id = companies[0].get("id")

        # --- Шаг 2: скачивание эмиссионных документов из БД (emission_documents) ---
        print(f"  [{secid}] Шаг 2/5: скачивание документов e-disclosure (ИНН + рег.номер)", flush=True)
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

        # --- Шаг 3: конвертация PDF → Markdown ---
        print(f"  [{secid}] Шаг 3/5: конвертация PDF → Markdown", flush=True)
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

        # --- Шаг 4: поиск событий ---
        print(f"  [{secid}] Шаг 4/5: поиск событий по рег.номеру", flush=True)
        events: List[Dict[str, Any]] = []
        if regnumber and regnumber.strip():
            try:
                events = find_events_by_reg_number(
                    date=date_str,
                    company_id=company_id,
                    reg_number=regnumber,
                )
            except Exception as exc:
                fl_logger.warning(
                    "[NOT FOUND] secid=%s: ошибка поиска событий: %s", secid, exc
                )

        # В events.json — полный текст и обработанный (для отладки); в LLM — только обработанный
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
