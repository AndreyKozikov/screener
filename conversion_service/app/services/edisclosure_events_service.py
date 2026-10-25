import logging
import re
from datetime import date, timedelta
from typing import Any, Dict, List, Optional

from app.repository.db.emitents_repository import EmitentsRepository
from app.repository.db.emitent_edisclosure_repository import EmitentEdisclosureRepository
from app.repository.files.file_storage import FileStorage
from app.utils.edisclosure.browser_event_fetcher import (
    EdisclosureAccessBlockedError,
    EdisclosureBrowserSession,
)
from app.utils.edisclosure_utils import merge_emitent_event_lists
from config.paths import EMITENT_EVENTS_JSON_DIR

logger = logging.getLogger(__name__)

_PROCESSING_STATE_KEY: str = "__processing_state"
_MAX_FORBIDDEN_RESTARTS: int = 3

class EdisclosureEventsService:
    """Сервис для загрузки и сохранения событий эмитентов."""

    def __init__(self) -> None:
        self._file_storage = FileStorage()
        self._emitents_repo = EmitentsRepository()
        self._emitent_edisclosure_repo = EmitentEdisclosureRepository()

    def _resolve_company_id_by_inn(
        self,
        inn: str,
        browser: EdisclosureBrowserSession,
    ) -> int:
        """Определяет ID компании на e-disclosure.
        
        Сначала проверяет локальный маппинг в БД. Если его нет, ищет в браузере.
        """
        print(f"[E-DISCLOSURE RESOLVE] Старт резолва company_id по ИНН={inn}", flush=True)
        emitent_id = self._emitents_repo.get_emitent_id_by_inn(inn)
        if emitent_id is not None:
            edisclosure_id = self._emitent_edisclosure_repo.get_edisclosure_id_by_emitent_id(emitent_id)
            if edisclosure_id is not None:
                print(f"[E-DISCLOSURE RESOLVE] edisclosure_id найден в таблице маппинга: {edisclosure_id}", flush=True)
                return int(edisclosure_id)

        print("[E-DISCLOSURE RESOLVE] Ищу компанию в окне браузера", flush=True)
        company_id = browser.resolve_company_id_by_inn(inn)
        
        # Сохраняем маппинг, если нашли emitent_id
        if emitent_id is not None:
            self._emitent_edisclosure_repo.upsert_mapping(emitent_id, int(company_id))
            
        print(f"[E-DISCLOSURE RESOLVE] Успех: финальный company_id={company_id}", flush=True)
        return int(company_id)

    def fetch_and_save_emitent_events_by_inn(self, inn: str) -> Dict[str, Any]:
        """Загружает ленту событий эмитента и сохраняет её в локальный JSON-кэш.
        
        Реализует инкрементальное обновление: если файл уже существует,
        догружаются только события текущего года.
        """
        inn_clean = inn.strip()
        if not re.fullmatch(r"\d{10}(?:\d{2})?", inn_clean):
            raise ValueError("Некорректный ИНН: ожидается 10 или 12 цифр.")

        with EdisclosureBrowserSession() as browser:
            restarts = 0
            while True:
                try:
                    return self._fetch_and_save_emitent_events(inn_clean, browser)
                except EdisclosureAccessBlockedError as exc:
                    if exc.status == 429:
                        raise
                    if restarts >= _MAX_FORBIDDEN_RESTARTS:
                        raise
                    restarts += 1
                    print(
                        f"  [ИНН {inn_clean}] Forbidden: очищаю данные сессии "
                        f"и повторяю с checkpoint ({restarts}/{_MAX_FORBIDDEN_RESTARTS}).",
                        flush=True,
                    )
                    if not browser.restart_after_block(exc):
                        raise

    def _fetch_and_save_emitent_events(
        self,
        inn_clean: str,
        browser: EdisclosureBrowserSession,
    ) -> Dict[str, Any]:
        """Run the event pipeline using an already-open browser session."""

        company_id = self._resolve_company_id_by_inn(inn_clean, browser)
        today = date.today()
        calendar_year_today = today.year
        out_path = EMITENT_EVENTS_JSON_DIR / f"{inn_clean}.json"
        EMITENT_EVENTS_JSON_DIR.mkdir(parents=True, exist_ok=True)

        raw_file: Optional[Dict[str, Any]] = None
        file_exists = False
        processing_state = None
        if out_path.exists():
            try:
                raw_file = self._file_storage.read_json(out_path)
                if isinstance(raw_file, dict) and raw_file:
                    file_exists = True
                    processing_state = raw_file.get(_PROCESSING_STATE_KEY)
            except Exception as exc:
                print(f"  [ИНН {inn_clean}] Не удалось прочитать {out_path}: {exc} — полная выгрузка", flush=True)
                raw_file = None

        resume_mode = False
        years_payload: Dict[str, Any] = {}
        years_processed: List[int] = []

        if file_exists and processing_state is not None and raw_file is not None:
            print(f"  [ИНН {inn_clean}] Обнаружен маркер незавершённой загрузки.", flush=True)
            years_payload = {str(yk): evs for yk, evs in raw_file.items() if isinstance(evs, list)}
            years_processed = sorted(processing_state.get("pending_years", []))
            resume_mode = True
        elif file_exists and raw_file is not None:
            resume_mode = True
            print(f"  [ИНН {inn_clean}] Файл найден — догрузка только за {calendar_year_today}", flush=True)
            years_payload = {str(yk): evs for yk, evs in raw_file.items() if isinstance(evs, list)}
            years_processed = [calendar_year_today]
        else:
            print(f"  [ИНН {inn_clean}] Полная выгрузка (список годов с портала)", flush=True)
            years_from_portal = browser.list_company_event_years(company_id)
            years_processed = sorted(set(years_from_portal + [calendar_year_today]))
            years_payload = {}

        counts_by_year = {}
        for y in years_processed:
            boundary = (today + timedelta(days=1)).isoformat() if y >= calendar_year_today else f"{y + 1}-01-01"
            print(f"  [ИНН {inn_clean}] Загружается год={y}, boundary_date={boundary}", flush=True)
            key = str(y)
            existing_events = years_payload.get(key, [])
            skip_pseudo_guids = {
                str(event.get("pseudoGUID"))
                for event in existing_events
                if isinstance(event, dict) and event.get("pseudoGUID")
            }
            try:
                year_events = browser.fetch_emitent_year_events(
                    company_id=company_id,
                    api_year=y,
                    boundary_date=boundary,
                    skip_pseudo_guids=skip_pseudo_guids,
                )
            except EdisclosureAccessBlockedError as exc:
                partial_events = exc.partial_events
                years_payload[key] = merge_emitent_event_lists(
                    existing_events if isinstance(existing_events, list) else [],
                    partial_events,
                )
                pending_years = sorted(
                    set([y] + [yr for yr in years_processed if yr > y])
                )
                save_payload = dict(years_payload)
                save_payload[_PROCESSING_STATE_KEY] = {
                    "pending_years": pending_years,
                    "company_id": company_id,
                }
                self._file_storage.write_json_durable(out_path, save_payload)
                exc.checkpoint_path = str(out_path)
                print(
                    f"  [ИНН {inn_clean}] Доступ заблокирован; сохранён checkpoint "
                    f"({len(years_payload[key])} событий за {y}).",
                    flush=True,
                )
                raise

            if resume_mode:
                prev = years_payload.get(key, [])
                years_payload[key] = merge_emitent_event_lists(prev, year_events)
            else:
                years_payload[key] = year_events
            
            counts_by_year[key] = len(years_payload[key])

            remaining_years = [yr for yr in years_processed if yr > y]
            save_payload = dict(years_payload)
            if remaining_years:
                save_payload[_PROCESSING_STATE_KEY] = {
                    "pending_years": remaining_years,
                    "company_id": company_id,
                }
            else:
                save_payload.pop(_PROCESSING_STATE_KEY, None)
            self._file_storage.write_json_durable(out_path, save_payload)
            print(f"  [ИНН {inn_clean}] Год {y} сохранён в файл", flush=True)

        return {
            "status": "ok",
            "inn": inn_clean,
            "company_id": company_id,
            "years_processed": years_processed,
            "counts_by_year": counts_by_year,
            "file_path": str(out_path)
        }

    def fetch_and_save_emitent_events_for_all_emitents(self) -> Dict[str, Any]:
        """Пакетное обновление лент событий для всех эмитентов в базе данных."""
        emitents = self._emitents_repo.get_emitents_with_inn()
        unique_inns = sorted(set(str(e["inn"]).strip() for e in emitents if e.get("inn")))
        
        print(f"[EMITENT EVENTS BATCH] Старт пакета: уникальных эмитентов (ИНН) к обработке: {len(unique_inns)}", flush=True)
        results = []
        errors = []
        if unique_inns:
            with EdisclosureBrowserSession() as browser:
                for num, inn in enumerate(unique_inns, start=1):
                    print(f"\n{'='*75}", flush=True)
                    print(f"[EMITENT EVENTS BATCH {num}/{len(unique_inns)}] Старт обработки ИНН: {inn}", flush=True)
                    print(f"{'='*75}", flush=True)
                    restarts = 0
                    while True:
                        try:
                            res = self._fetch_and_save_emitent_events(inn, browser)
                            results.append(res)
                            print(f"[EMITENT EVENTS BATCH {num}/{len(unique_inns)}] ИНН {inn} -> УСПЕХ", flush=True)
                            break
                        except EdisclosureAccessBlockedError as exc:
                            if exc.status == 429:
                                errors.append(
                                    {
                                        "inn": inn,
                                        "detail": str(exc),
                                        "support_report": exc.support_report,
                                        "checkpoint_path": exc.checkpoint_path,
                                    }
                                )
                                print(
                                    "[EMITENT EVENTS BATCH] Получено HTTP 429; "
                                    "останавливаю пакет без сброса сессии.",
                                    flush=True,
                                )
                                break
                            if restarts < _MAX_FORBIDDEN_RESTARTS:
                                restarts += 1
                                print(
                                    f"[EMITENT EVENTS BATCH] Очищаю данные сессии и "
                                    f"возобновляю ИНН {inn} ({restarts}/{_MAX_FORBIDDEN_RESTARTS}).",
                                    flush=True,
                                )
                                if browser.restart_after_block(exc):
                                    continue

                            browser.clear_authorization_data(exc)
                            errors.append(
                                {
                                    "inn": inn,
                                    "detail": str(exc),
                                    "support_report": exc.support_report,
                                    "checkpoint_path": exc.checkpoint_path,
                                }
                            )
                            print(
                                "[EMITENT EVENTS BATCH] Останавливаю пакет после исчерпания "
                                "повторных запусков.",
                                flush=True,
                            )
                            break
                        except Exception as exc:
                            print(f"[EMITENT EVENTS BATCH {num}/{len(unique_inns)}] ИНН {inn} -> ОШИБКА: {exc}", flush=True)
                            errors.append({"inn": inn, "detail": str(exc)})
                            break

                    if errors and errors[-1].get("inn") == inn and "support_report" in errors[-1]:
                        break

        return {
            "status": "ok" if not errors else "partial_error",
            "processed": len(unique_inns),
            "succeeded": len(results),
            "failed": len(errors),
            "errors": errors
        }

_service: Optional[EdisclosureEventsService] = None

def get_edisclosure_events_service() -> EdisclosureEventsService:
    """Возвращает синглтон сервиса."""
    global _service
    if _service is None:
        _service = EdisclosureEventsService()
    return _service
