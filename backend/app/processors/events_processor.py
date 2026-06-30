from typing import Any, Dict, List, Optional, Set
from app.parsers.emission_series_parser import filter_events_by_secid_regnumber_series
from app.utils.edisclosure_utils import clean_event_text
from app.utils.datetime_utils import compute_event_years
from datetime import date, datetime
from pathlib import Path


class EventsProcessor:
    """Сервис для загрузки, фильтрации и подготовки событий раскрытия информации."""

    def __init__(
            self,
            db_evens_path: Path,
            base_dir: Path,
    ) -> None:
        from app.repository.db.event_detail_repository import get_events_detail_repository
        from app.repository.files import get_file_storage

        self._file_storage = get_file_storage()
        self._event_detail_repo = get_events_detail_repository(db_evens_path)
        self._base_dir = base_dir
        self._allowed_event_types: Set[str] = {
            "размещение",
            "регистрация",
            "ставка купона",
            "выплата купона",
            "оферта",
        }

    def get_prepared_events(
            self,
            secid: str,
            inn: str,
            regnumber: Optional[str],
            series: Optional[str],
            date_str: str,
            use_local_events: bool,
            filter_event_by_type: bool = False,
    ) -> List[Dict[str, Any]]:
        """Полный цикл подготовки событий: загрузка, фильтрация по метаданным,

        фильтрация по типам из БД и очистка текста.
        """
        # 1. Загрузка
        event_years = compute_event_years(date_str)

        all_events = self.load_events_from_local_file(inn=inn, years=event_years)

        # 2. Первичная фильтрация
        events = filter_events_by_secid_regnumber_series(
            all_events, secid or "", regnumber or "", series
        )

        # 3. Фильтрация по event_type из БД
        if filter_event_by_type:
            events = self._filter_by_db_type(events, secid)

        # 4. Очистка текста
        for e in events:
            full = e.get("full_text", "")
            e["text"] = clean_event_text(full)

        return events

    def _filter_by_db_type(self, events: List[Dict[str, Any]], secid: str) -> List[Dict[str, Any]]:
        """Внутренний метод фильтрации по типам событий."""
        filtered_events: List[Dict[str, Any]] = []
        for e in events:
            pseudo_guid = e.get("pseudo_guid")
            event_date = e.get("event_date")

            if pseudo_guid and event_date:
                dt_str = str(event_date)[:10]
                detail = self._event_detail_repo.get_by_guid_and_date(pseudo_guid, dt_str)
                if detail is None:
                    filtered_events.append(e)
                else:
                    evt_type = (detail.event_type or "").strip().lower()
                    if evt_type in self._allowed_event_types:
                        filtered_events.append(e)
            else:
                filtered_events.append(e)
        return filtered_events

    def load_events_from_local_file(
        self,
        inn: str,
        years: List[int],
    ) -> List[Dict[str, Any]]:
        """Загружает и предварительно обрабатывает ленту событий из локального кэша."""
        events_file: Path = self._base_dir / f"{inn}.json"
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
                "pseudo_guid": ev.get("pseudoGUID"),
                "full_text": full_text,
                "text": processed_text,
            })
        return result