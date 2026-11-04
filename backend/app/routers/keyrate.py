"""Read-only API for key-rate data stored in the database."""

import asyncio
from datetime import date
from typing import Any, List

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response

from app.services.keyrate_service import get_keyrate_service

router = APIRouter(prefix="/api/keyrate", tags=["keyrate"])


def _parse_iso_date(value: str | None, param_name: str) -> date | None:
    if value is None or not value.strip():
        return None
    try:
        return date.fromisoformat(value.strip())
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid {param_name} format. Use ISO date (YYYY-MM-DD).",
        ) from exc


@router.get("/data")
async def get_keyrate_data(
    from_: str | None = Query(None, alias="from"),
    till: str | None = Query(None),
) -> List[dict[str, Any]]:
    try:
        rows = await asyncio.to_thread(
            get_keyrate_service().get_keyrate_list,
            _parse_iso_date(from_, "from"),
            _parse_iso_date(till, "till"),
        )
        return [row.model_dump(by_alias=True, mode="json") for row in rows]
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to get key rate data: {exc}") from exc


@router.get("/download/markdown")
async def download_keyrate_markdown(
    from_: str | None = Query(None, alias="from"),
    till: str | None = Query(None),
) -> Response:
    from_date = _parse_iso_date(from_, "from")
    till_date = _parse_iso_date(till, "till")
    rows = await asyncio.to_thread(
        get_keyrate_service().get_keyrate_list,
        from_date,
        till_date,
    )
    if not rows:
        raise HTTPException(status_code=404, detail="No data found for the specified date range")
    columns = ["Дата", "Ключевая ставка, % годовых"]
    lines = ["# Ключевая ставка ЦБ", "", "| " + " | ".join(columns) + " |", "| --- | --- |"]
    for record in rows:
        row = record.model_dump(by_alias=True, mode="json")
        values = [
            f"{row.get(column):.2f}" if isinstance(row.get(column), float) else str(row.get(column) or "")
            for column in columns
        ]
        lines.append("| " + " | ".join(values) + " |")
    filename = f"keyrate_{from_ or 'all'}_{till or 'all'}.md"
    return Response(
        content="\n".join(lines),
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
