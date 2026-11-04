"""Endpoints for importing Bank of Russia forecast documents."""

import re
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile

from conversion_service.app.core.exceptions import PdfConversionConnectionError
from conversion_service.app.services.forecast_service import get_forecast_service
from conversion_service.config.paths import DATA_DIR

router = APIRouter(prefix="/forecast", tags=["forecast-import"])


@router.post("/upload")
async def upload_forecast_pdf(
    file: UploadFile = File(..., description="PDF file with Bank of Russia forecast (.pdf)"),
):
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=400,
            detail=f"Разрешён только формат PDF (.pdf). Получено: {file.filename or 'без имени'}",
        )
    safe_name = re.sub(r"[^\w.\-]", "_", file.filename)
    if not safe_name.lower().endswith(".pdf"):
        safe_name = safe_name.rstrip("_") + ".pdf"
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    destination = DATA_DIR / safe_name
    try:
        destination.write_bytes(await file.read())
        get_forecast_service().process_pdf_and_save(safe_name)
    except PdfConversionConnectionError as exc:
        raise HTTPException(status_code=503, detail=f"Сервис конвертации недоступен: {exc}") from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except OSError as exc:
        raise HTTPException(status_code=500, detail=f"Ошибка записи файла: {exc}") from exc

    return {
        "filename": safe_name,
        "md_file": Path(safe_name).stem + ".md",
        "saved_to": str(destination),
    }
