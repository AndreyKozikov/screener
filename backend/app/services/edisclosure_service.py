"""Сервис для работы с e-disclosure.ru.

Содержит логику вызова методов из edisclosure_utils: поиск компаний по ИНН,
поиск событий по регистрационному номеру облигации и скачивание документов
из дерева раскрытия MOEX.
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
from app.utils.edisclosure_utils import (
    fetch_moex_disclosure_docs,
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

    Оркестрирует вызовы search_company_by_inn, find_events_by_reg_number
    и fetch_moex_disclosure_docs. Использует bonds_service для получения
    ИНН, регномера и MOEX ID по secid, TradingHistoryService — для получения
    наименьшей даты из истории торгов. Скачанные PDF сохраняет через FileStorage.
    """

    def __init__(self) -> None:
        self._file_storage: FileStorage = FileStorage()
        self._float_params_repo: BondFloatParamsRepository = BondFloatParamsRepository()
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
        Дополнительно скачивает PDF-документы через MOEX disclosure tree API,
        конвертирует их в Markdown и передаёт в GeminiAnalysisService.
        Файлы сохраняются в подпапку backend/app/data/{secid}.

        Args:
            inn: ИНН компании.
            date: Граничная дата в формате YYYY-MM-DD; включаются события строго раньше неё.
            regnumber: Регистрационный номер облигации (опционально).
            emitent_moex_id: MOEX ID эмитента для навигации по дереву раскрытия (опционально).
            secid: Идентификатор облигации для подпапки данных.

        Returns:
            Валидированный GeminiBondAnalysisDTO или None при ошибке анализа.

        Raises:
            ValueError: Компания не найдена или не удалось получить ID.
        """
        bond_data_dir: Path = _DATA_DIR / (secid or "unknown")
        bond_data_dir.mkdir(parents=True, exist_ok=True)

        # --- Шаг 1: поиск компании на e-disclosure.ru ---
        logger.info(
            "[E-DISCLOSURE] → POST https://www.e-disclosure.ru/api/search/companies"
            " | ИНН=%s",
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

        # --- Шаг 2: поиск событий по регистрационному номеру ---
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

        events_file: Path = bond_data_dir / "events.json"
        self._file_storage.save_text_file(
            events_file,
            json.dumps(events, ensure_ascii=False, indent=2),
        )
        logger.info("[E-DISCLOSURE EVENTS] Сохранён файл событий: %s", events_file)

        # --- Шаг 3: скачивание документов с MOEX ---
        doc_filenames: List[str] = []
        if regnumber and regnumber.strip() and emitent_moex_id is not None:
            logger.info(
                "[MOEX DOCS] → GET https://web.moex.com/moex-web-icdb-api/api/v1/"
                "bond-disclosure-tree/reporting/%s | рег.номер=%s",
                emitent_moex_id, regnumber,
            )
            downloaded: List[Tuple[str, bytes]] = fetch_moex_disclosure_docs(
                emitent_id=emitent_moex_id,
                reg_number=regnumber,
            )
            for filename, content in downloaded:
                self._file_storage.save_binary_file(bond_data_dir / filename, content)
                doc_filenames.append(filename)
                print(f"[MOEX DOCS] Сохранён PDF: {filename} ({len(content)} байт)", flush=True)
            logger.info(
                "[MOEX DOCS] Скачано PDF-файлов: %d → %s",
                len(doc_filenames), doc_filenames,
            )
        else:
            logger.info(
                "[MOEX DOCS] Пропуск: рег.номер=%s, emitent_moex_id=%s",
                regnumber, emitent_moex_id,
            )

        # --- Шаг 4: конвертация PDF → Markdown ---
        result: Dict[str, Any] = {
            "companies": companies,
            "events": events,
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

        # --- Шаг 5: анализ через LLM (с повтором при 503 UNAVAILABLE) ---
        logger.info("[LLM] Передача данных на анализ (провайдер: %s)...", provider)
        return self._call_llm_with_retry(converted, provider)

    # ------------------------------------------------------------------
    # Пакетная обработка всех флоатеров
    # ------------------------------------------------------------------

    def update_all_floaters(self, provider: str = "gemini") -> None:
        """Обрабатывает облигации вида «флоатер» (bond_kind=8), ещё не сохранённые.

        Получает полный список secid флоатеров, фильтрует уже обработанные
        (существующие в bond_float_params), затем для каждого оставшегося
        выполняет полный пайплайн: поиск компании, поиск событий, скачивание
        документов, конвертация PDF→MD, анализ LLM.
        Ограничение: не более 7 запросов к LLM в минуту.

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

    def _process_single_floater(
        self, secid: str, fl_logger: logging.Logger, provider: str = "gemini",
    ) -> bool:
        """Выполняет полный пайплайн анализа для одной облигации-флоатера.

        regnumber и emitent_moex_id не передаются в метод — получаются из БД
        по secid (get_reg_number_by_secid, get_emitent_moex_id_by_secid).
        Скачивание с MOEX выполняется только если оба значения заданы в БД.

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

        # --- Шаг 1: поиск компании ---
        print(f"  [{secid}] Шаг 1/5: поиск компании на e-disclosure (ИНН={inn})", flush=True)
        try:
            companies: List[Dict[str, Any]] = search_company_by_inn(inn)
        except Exception as exc:
            fl_logger.warning(
                "[NOT FOUND] secid=%s: ошибка поиска компании: %s", secid, exc
            )
            if bond_id is not None:
                self._float_params_repo.upsert_not_found(bond_id, _get_not_found_float_params_data())
            return False

        if not companies:
            fl_logger.warning(
                "[NOT FOUND] secid=%s: компания с ИНН=%s не найдена на e-disclosure",
                secid, inn,
            )
            if bond_id is not None:
                self._float_params_repo.upsert_not_found(bond_id, _get_not_found_float_params_data())
            return False

        company_id: Any = companies[0].get("id")

        # --- Шаг 2: поиск событий ---
        print(f"  [{secid}] Шаг 2/5: поиск событий по рег.номеру", flush=True)
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

        events_file_batch: Path = bond_data_dir / "events.json"
        self._file_storage.save_text_file(
            events_file_batch,
            json.dumps(events, ensure_ascii=False, indent=2),
        )

        # --- Шаг 3: скачивание документов ---
        print(f"  [{secid}] Шаг 3/5: скачивание документов MOEX", flush=True)
        doc_filenames: List[str] = []
        if regnumber and regnumber.strip() and emitent_moex_id is not None:
            try:
                downloaded: List[Tuple[str, bytes]] = fetch_moex_disclosure_docs(
                    emitent_id=emitent_moex_id,
                    reg_number=regnumber,
                )
                for filename, content in downloaded:
                    self._file_storage.save_binary_file(bond_data_dir / filename, content)
                    doc_filenames.append(filename)
                    print(f"[MOEX DOCS] Сохранён PDF: {filename} ({len(content)} байт)", flush=True)
            except Exception as exc:
                fl_logger.warning(
                    "[NOT FOUND] secid=%s: ошибка скачивания документов: %s", secid, exc
                )

        if not events and not doc_filenames:
            fl_logger.warning(
                "[NOT FOUND] secid=%s: не найдено ни событий (%d), ни документов (%d)",
                secid, len(events), len(doc_filenames),
            )
            if bond_id is not None:
                self._float_params_repo.upsert_not_found(bond_id, _get_not_found_float_params_data())
            return False

        # --- Шаг 4: PDF → MD ---
        print(f"  [{secid}] Шаг 4/5: конвертация PDF → Markdown", flush=True)
        result_dict: Dict[str, Any] = {
            "companies": companies,
            "events": events,
            "regnumber": regnumber,
            "search_date": date_str,
            "doc_filenames": doc_filenames,
            "data_dir": bond_data_dir,
        }
        converted: Dict[str, Any] = get_pdf_conversion_service().convert(result_dict)
        converted["fallback_inn"] = inn
        md_filenames_batch: List[str] = converted.get("md_filenames", [])
        for md_name in md_filenames_batch:
            print(f"[PDF2MD] Создан Markdown: {md_name}", flush=True)

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
