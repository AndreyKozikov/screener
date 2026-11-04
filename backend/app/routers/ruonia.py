"""Read-only API for RUONIA data stored in the database."""

import asyncio
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response

from app.models import RuoniaDataResponse
from app.services.ruonia_service import get_ruonia_service

router = APIRouter(prefix="/api/ruonia", tags=["ruonia"])


@router.get("/data", response_model=RuoniaDataResponse, response_model_by_alias=True)
async def get_ruonia_data(
    date_from: Optional[str] = Query(None, description="Start date DD.MM.YYYY"),
    date_to: Optional[str] = Query(None, description="End date DD.MM.YYYY"),
) -> RuoniaDataResponse:
    try:
        return await asyncio.to_thread(
            get_ruonia_service().get_ruonia_data,
            date_from=date_from,
            date_to=date_to,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to get RUONIA data: {exc}") from exc


@router.get("/download/markdown")
async def download_ruonia_markdown(
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
) -> Response:
    try:
        content = await asyncio.to_thread(
            get_ruonia_service().export_markdown,
            date_from=date_from,
            date_to=date_to,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to generate Markdown: {exc}") from exc
    filename = "ruonia"
    if date_from or date_to:
        if date_from:
            filename += f"_{date_from.replace('.', '-')}"
        if date_to:
            filename += f"_{date_to.replace('.', '-')}"
    else:
        filename += "_all"
    return Response(
        content=content,
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}.md"'},
    )
