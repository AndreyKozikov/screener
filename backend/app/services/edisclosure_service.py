"""Read local e-disclosure event data for bond analysis."""

from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from app.repository.db.emitent_edisclosure_repository import EmitentEdisclosureRepository
from app.repository.db.emitents_repository import EmitentsRepository
from app.repository.files.file_storage import FileStorage
from app.utils.datetime_utils import compute_event_years
from app.utils.edisclosure_utils import clean_event_text, search_company_by_inn
from config.paths import EMITENT_EVENTS_JSON_DIR


class EdisclosureService:
    """Resolve issuer event context and read the downloaded event cache."""

    def __init__(self) -> None:
        self._emitents_repo = EmitentsRepository()
        self._mapping_repo = EmitentEdisclosureRepository()
        self._file_storage = FileStorage()

    def _resolve_company_id_by_inn(self, inn: str) -> Tuple[int, List[Dict[str, Any]]]:
        emitent_id = self._emitents_repo.get_emitent_id_by_inn(inn)
        if emitent_id is not None:
            edisclosure_id = self._mapping_repo.get_edisclosure_id_by_emitent_id(emitent_id)
            if edisclosure_id is not None:
                return int(edisclosure_id), [{"id": int(edisclosure_id), "name": ""}]

        companies = search_company_by_inn(inn)
        if not companies:
            raise ValueError(f"Компания с ИНН {inn} не найдена на e-disclosure.ru")
        raw_id = companies[0].get("id")
        if raw_id is None:
            raise ValueError("Не удалось получить ID компании из ответа e-disclosure")
        try:
            company_id = int(raw_id)
        except (TypeError, ValueError) as exc:
            raise ValueError("Не удалось получить ID компании из ответа e-disclosure") from exc
        return company_id, companies

    def _compute_event_years(self, date_str: str) -> List[int]:
        return compute_event_years(date_str)

    def _load_events_from_local_file(self, inn: str, years: List[int]) -> List[Dict[str, Any]]:
        path = EMITENT_EVENTS_JSON_DIR / f"{inn}.json"
        if not path.is_file():
            return []
        try:
            raw_data = self._file_storage.read_json(path)
        except Exception:
            return []
        if not isinstance(raw_data, dict):
            return []

        allowed_years = {str(year) for year in years}
        events: List[Dict[str, Any]] = []
        for year, items in raw_data.items():
            if year not in allowed_years or not isinstance(items, list):
                continue
            for item in items:
                if not isinstance(item, dict):
                    continue
                event_date = item.get("event_date") or item.get("eventDate")
                if not event_date:
                    continue
                try:
                    parsed_date = datetime.strptime(str(event_date)[:10], "%Y-%m-%d").date()
                except (ValueError, TypeError):
                    continue
                full_text = item.get("full_text") or item.get("text") or ""
                events.append({
                    "event_name": item.get("event_name") or item.get("eventName") or "",
                    "event_date": event_date,
                    "pseudo_guid": item.get("pseudoGUID") or item.get("pseudo_guid"),
                    "full_text": full_text,
                    "text": clean_event_text(full_text),
                    "_sort_date": parsed_date,
                })
        events.sort(key=lambda event: event["_sort_date"], reverse=True)
        for event in events:
            event.pop("_sort_date", None)
        return events


_edisclosure_service: Optional[EdisclosureService] = None


def get_edisclosure_service() -> EdisclosureService:
    global _edisclosure_service
    if _edisclosure_service is None:
        _edisclosure_service = EdisclosureService()
    return _edisclosure_service
