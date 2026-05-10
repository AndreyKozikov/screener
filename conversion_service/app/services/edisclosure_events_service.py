import logging
import re
import json
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from app.repository.db.emitents_repository import EmitentsRepository
from app.repository.db.emitent_edisclosure_repository import EmitentEdisclosureRepository
from app.repository.files.file_storage import FileStorage
from app.utils.edisclosure_utils import (
    fetch_emitent_year_events_unfiltered,
    find_latest_event_metadata_across_years,
    list_company_portal_event_years,
    merge_emitent_event_lists,
    search_company_by_inn,
)
from config.paths import EMITENT_EVENTS_JSON_DIR

logger = logging.getLogger(__name__)

_PROCESSING_STATE_KEY: str = "__processing_state"

class EdisclosureEventsService:
    """Сервис для загрузки и сохранения событий эмитентов."""

    def __init__(self) -> None:
        self._file_storage = FileStorage()
        self._emitents_repo = EmitentsRepository()
        self._emitent_edisclosure_repo = EmitentEdisclosureRepository()

    def _resolve_company_id_by_inn(self, inn: str) -> int:
        """Определяет ID компании на e-disclosure.
        
        Сначала проверяет локальный маппинг в БД. Если не найден, ищет через API.
        """
        print(f"[E-DISCLOSURE RESOLVE] Старт резолва company_id по ИНН={inn}", flush=True)
        emitent_id = self._emitents_repo.get_emitent_id_by_inn(inn)
        if emitent_id is not None:
            edisclosure_id = self._emitent_edisclosure_repo.get_edisclosure_id_by_emitent_id(emitent_id)
            if edisclosure_id is not None:
                print(f"[E-DISCLOSURE RESOLVE] edisclosure_id найден в таблице маппинга: {edisclosure_id}", flush=True)
                return int(edisclosure_id)

        print("[E-DISCLOSURE RESOLVE] Переход к fallback: поиск компании через API e-disclosure", flush=True)
        companies = search_company_by_inn(inn)
        if not companies:
            print(f"[E-DISCLOSURE RESOLVE] Ошибка: компания с ИНН={inn} не найдена", flush=True)
            raise ValueError(f"Компания с ИНН {inn} не найдена на e-disclosure.ru")
        
        company_id = companies[0].get("id")
        if company_id is None:
            print("[E-DISCLOSURE RESOLVE] Ошибка: у первой компании отсутствует id", flush=True)
            raise ValueError("Не удалось получить ID компании из ответа e-disclosure")
        
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

        company_id = self._resolve_company_id_by_inn(inn_clean)
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
                print(f"[EMITENT EVENTS] Не удалось прочитать {out_path}: {exc} — полная выгрузка", flush=True)
                raw_file = None

        resume_mode = False
        years_payload: Dict[str, Any] = {}
        years_processed: List[int] = []

        if file_exists and processing_state is not None and raw_file is not None:
            print(f"[EMITENT EVENTS] Обнаружен маркер незавершённой загрузки.", flush=True)
            years_payload = {str(yk): evs for yk, evs in raw_file.items() if isinstance(evs, list)}
            years_processed = sorted(processing_state.get("pending_years", []))
        elif file_exists and raw_file is not None:
            resume_mode = True
            print(f"[EMITENT EVENTS] Файл найден — догрузка только за {calendar_year_today}", flush=True)
            years_payload = {str(yk): evs for yk, evs in raw_file.items() if isinstance(evs, list)}
            years_processed = [calendar_year_today]
        else:
            print("[EMITENT EVENTS] Полная выгрузка (список годов с портала)", flush=True)
            years_from_portal = list_company_portal_event_years(company_id)
            years_processed = sorted(set(years_from_portal + [calendar_year_today]))
            years_payload = {}

        counts_by_year = {}
        for y in years_processed:
            boundary = (today + timedelta(days=1)).isoformat() if y >= calendar_year_today else f"{y + 1}-01-01"
            print(f"[EMITENT EVENTS] Загружается год={y}, boundary_date={boundary}", flush=True)
            year_events = fetch_emitent_year_events_unfiltered(company_id=company_id, api_year=y, boundary_date=boundary)
            
            key = str(y)
            if resume_mode:
                prev = years_payload.get(key, [])
                years_payload[key] = merge_emitent_event_lists(prev, year_events)
            else:
                years_payload[key] = year_events
            
            counts_by_year[key] = len(years_payload[key])

            # Инкрементальное сохранение
            if not resume_mode:
                remaining_years = [yr for yr in years_processed if yr > y]
                save_payload = dict(years_payload)
                if remaining_years:
                    save_payload[_PROCESSING_STATE_KEY] = {"pending_years": remaining_years, "company_id": company_id}
                self._file_storage.write_json_durable(out_path, save_payload)
                print(f"[EMITENT EVENTS] Год {y} сохранён в файл", flush=True)

        if resume_mode:
            self._file_storage.write_json_durable(out_path, years_payload)
            print(f"[EMITENT EVENTS] Файл обновлён (resume_mode)", flush=True)

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
        for num, inn in enumerate(unique_inns, start=1):
            try:
                res = self.fetch_and_save_emitent_events_by_inn(inn)
                results.append(res)
                print(f"[EMITENT EVENTS BATCH] ИНН={inn}: выгрузка завершена ({num}/{len(unique_inns)})", flush=True)
            except Exception as e:
                print(f"[EMITENT EVENTS BATCH] ИНН={inn}: ошибка ({num}/{len(unique_inns)}) — {e}", flush=True)
                errors.append({"inn": inn, "detail": str(e)})

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
