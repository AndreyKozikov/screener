"""Router for Pipeline 1 — emission document download and conversion."""

from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Query

from app.core.exceptions import PdfConversionConnectionError
from app.services.emission_doc_download_service import get_emission_doc_download_service

router = APIRouter(prefix="/emission-doc-download", tags=["emission-doc-download"])


@router.post("/run")
async def run_download_pipeline(
    secid: Optional[str] = Query(
        None,
        description="SECID of a specific bond. "
        "If provided — downloads and converts documents only for this bond. "
        "If not provided — processes all unprocessed bonds.",
    ),
    limit: Optional[int] = Query(
        None,
        description="Maximum number of bonds to process. None — all unprocessed / failed.",
    ),
    rating: Optional[str] = Query(
        None,
        description="Filter by bond credit rating (e.g. AAA, AA+, BBB). "
        "If not set — all bonds are processed.",
    ),
) -> Dict[str, Any]:
    """Download emission documents and convert ALL to Markdown.

    Pipeline 1: downloads ZIP archives from e-disclosure emission_documents table,
    extracts files, and converts every document to Markdown (no filters applied).

    Two modes:
    - Initial load: processes all bonds without a data directory.
    - Update: re-processes only bonds that previously failed (no .md files in data dir).

    If ``secid`` is provided, processes only the bond with that SECID.
    """
    try:
        service = get_emission_doc_download_service()
        return service.download_and_convert(
            secid=secid,
            limit=limit,
            rating=rating,
        )
    except PdfConversionConnectionError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"PDF conversion service unavailable: {exc}",
        ) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Error during document download pipeline: {exc}",
        ) from exc
