"""Update the zero-coupon yield curve from MOEX and save it to the database."""

import json
import logging
import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import httpx

from conversion_service.app.repository.db.remote_repository import KbdRepository

logger = logging.getLogger(__name__)

_API_PERIOD_TO_TERM = {
    0.25: "term_0_25", 0.5: "term_0_5", 0.75: "term_0_75", 1.0: "term_1_0",
    2.0: "term_2_0", 3.0: "term_3_0", 5.0: "term_5_0", 7.0: "term_7_0",
    10.0: "term_10_0", 15.0: "term_15_0", 20.0: "term_20_0", 30.0: "term_30_0",
}


def _parse_jsonp_response(text: str) -> Dict[str, Any]:
    match = re.match(r"^\s*JSON_CALLBACK\s*\((.*)\)\s*$", text, re.DOTALL)
    json_str = match.group(1) if match else text
    try:
        return json.loads(json_str)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Failed to parse JSON: {exc}") from exc


def _api_yields_to_dbkbd(
    date_obj: datetime,
    time_str: str,
    yields_data: List[Dict[str, Any]],
) -> Dict[str, Any]:
    time_str = time_str.split(" ")[-1] if " " in time_str else time_str
    if len(time_str.split(":")) == 2:
        time_str += ":00"
    row: Dict[str, Any] = {"date": date_obj.strftime("%Y-%m-%d"), "time": time_str}
    row.update({term: None for term in _API_PERIOD_TO_TERM.values()})
    for item in yields_data:
        period = item.get("period")
        value = item.get("value")
        if period in _API_PERIOD_TO_TERM and value is not None:
            try:
                row[_API_PERIOD_TO_TERM[period]] = float(value)
            except (TypeError, ValueError):
                pass
    return row


class ZerocuponUpdateService:
    API_URL = "https://iss.moex.com/iss/engines/stock/zcyc.jsonp"

    def __init__(self, repository: Optional[KbdRepository] = None) -> None:
        self._repo = repository or KbdRepository()

    def _fetch_for_date(self, target_date: datetime) -> Optional[List[Dict[str, Any]]]:
        date_str = target_date.strftime("%Y-%m-%d")
        url = (
            f"{self.API_URL}?iss.meta=off&iss.json=extended&callback=JSON_CALLBACK"
            f"&lang=ru&iss.only=yearyields&date={date_str}"
        )
        logger.info("[REFRESH ZEROCOUPON] Fetching data from API: %s", url)
        try:
            with httpx.Client(timeout=30.0) as client:
                response = client.get(url)
                response.raise_for_status()
                payload = _parse_jsonp_response(response.text)
            if isinstance(payload, list) and len(payload) >= 2:
                for item in payload:
                    if isinstance(item, dict) and "yearyields" in item:
                        return item["yearyields"]
            return None
        except Exception as exc:
            logger.error("[REFRESH ZEROCOUPON] Error fetching data for %s from %s: %s", date_str, url, exc)
            return None

    def refresh(self) -> Dict[str, Any]:
        logger.info("[REFRESH ZEROCOUPON] Starting zerocupon data refresh (API → DB)")
        last_date = self._repo.get_last_kbd_date()
        start_date = last_date + timedelta(days=1) if last_date else datetime.now() - timedelta(days=30)
        end_date = datetime.now() - timedelta(days=1)
        if start_date > end_date:
            return {
                "status": "ok", "message": "Data is up to date",
                "last_date": last_date.strftime("%d.%m.%Y") if last_date else None,
                "dates_fetched": 0,
            }

        records: List[Dict[str, Any]] = []
        dates_fetched = 0
        dates_failed = 0
        current_date = start_date
        while current_date <= end_date:
            if current_date.weekday() < 5:
                yields = self._fetch_for_date(current_date)
                if yields:
                    time_str = yields[0].get("tradetime", "18:49:59")
                    records.append(_api_yields_to_dbkbd(current_date, time_str, yields))
                    dates_fetched += 1
                else:
                    dates_failed += 1
            current_date += timedelta(days=1)

        if records:
            self._repo.save_kbd_records(records)
        return {
            "status": "ok",
            "message": f"Fetched {dates_fetched} dates, {dates_failed} failed",
            "last_date": last_date.strftime("%d.%m.%Y") if last_date else None,
            "start_date": start_date.strftime("%d.%m.%Y"),
            "end_date": end_date.strftime("%d.%m.%Y"),
            "dates_fetched": dates_fetched,
            "dates_failed": dates_failed,
        }


_service: Optional[ZerocuponUpdateService] = None


def get_zerocupon_update_service() -> ZerocuponUpdateService:
    global _service
    if _service is None:
        _service = ZerocuponUpdateService()
    return _service
