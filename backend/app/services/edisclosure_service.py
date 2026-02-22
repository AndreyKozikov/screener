"""Сервис для работы с e-disclosure.ru.

Содержит логику вызова методов из edisclosure_utils: поиск компаний по ИНН,
поиск событий по регистрационному номеру облигации и скачивание документов
из дерева раскрытия MOEX.
Эндпоинт вызывает get_accrued_income_by_secid(secid), который после получения
результата анализа от Gemini сохраняет данные в БД через BondFloatParamsRepository
и удаляет временные файлы из _DATA_DIR.
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from app.models.schemasDTO.gemini_dto import GeminiBondAnalysisDTO
from app.repository.db.bond_float_params_repository import BondFloatParamsRepository
from app.repository.files.file_storage import FileStorage
from app.services.bonds_service import (
    get_bond_id_by_secid,
    get_emitent_inn_by_secid,
    get_emitent_moex_id_by_secid,
    get_reg_number_by_secid,
)
from app.services.gemini_analysis_service import get_gemini_analysis_service
from app.services.pdf_conversion_service import get_pdf_conversion_service
from app.services.trading_history_service import get_trading_history_service
from app.utils.edisclosure_utils import (
    fetch_moex_disclosure_docs,
    find_events_by_reg_number,
    search_company_by_inn,
)

logger: logging.Logger = logging.getLogger(__name__)

_DEFAULT_DATE: str = "2025-04-24"
_DATA_DIR: Path = Path(__file__).resolve().parent.parent / "data"


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

    def get_accrued_income_by_secid(self, secid: str) -> Dict[str, str]:
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

        analysis: Optional[GeminiBondAnalysisDTO] = self._get_accrued_income_by_inn(
            inn=inn,
            date=date_str,
            regnumber=regnumber,
            emitent_moex_id=emitent_moex_id,
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
        self._file_storage.delete_files_by_pattern(
            directory=_DATA_DIR,
            extensions=("*.pdf", "*.md"),
        )

    def _get_accrued_income_by_inn(
        self,
        inn: str,
        date: str = "2025-04-24",
        regnumber: Optional[str] = None,
        emitent_moex_id: Optional[int] = None,
    ) -> Optional[GeminiBondAnalysisDTO]:
        """Получает данные компании по ИНН, скачивает документы и анализирует их через Gemini.

        Вызывает search_company_by_inn для получения ID компании, затем
        find_events_by_reg_number для поиска всех событий года, в которых
        присутствует регистрационный номер облигации или его части.
        Если regnumber не задан — возвращает пустой список событий.
        Дополнительно скачивает PDF-документы через MOEX disclosure tree API,
        конвертирует их в Markdown и передаёт в GeminiAnalysisService.

        Args:
            inn: ИНН компании.
            date: Граничная дата в формате YYYY-MM-DD; включаются события строго раньше неё.
            regnumber: Регистрационный номер облигации (опционально).
            emitent_moex_id: MOEX ID эмитента для навигации по дереву раскрытия (опционально).

        Returns:
            Валидированный GeminiBondAnalysisDTO или None при ошибке анализа.

        Raises:
            ValueError: Компания не найдена или не удалось получить ID.
        """
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
                self._file_storage.save_binary_file(_DATA_DIR / filename, content)
                doc_filenames.append(filename)
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
        }
        if doc_filenames:
            logger.info(
                "[PDF2MD] → POST %s/api/v1/convert | PDF-файлов: %d → %s",
                "http://localhost:9000",
                len(doc_filenames), doc_filenames,
            )
        converted: Dict[str, Any] = get_pdf_conversion_service().convert(result)
        md_filenames: List[str] = converted.get("md_filenames", [])
        logger.info(
            "[PDF2MD] Создано Markdown-файлов: %d → %s",
            len(md_filenames), md_filenames,
        )

        # --- Шаг 5: анализ через Gemini ---
        logger.info("[GEMINI] Передача данных на анализ...")
        return get_gemini_analysis_service().analyze(converted)


_edisclosure_service: Optional[EdisclosureService] = None


def get_edisclosure_service() -> EdisclosureService:
    """Возвращает singleton EdisclosureService."""
    global _edisclosure_service
    if _edisclosure_service is None:
        _edisclosure_service = EdisclosureService()
    return _edisclosure_service
