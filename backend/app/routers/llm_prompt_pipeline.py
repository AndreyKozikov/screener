"""Router for Pipeline 2 — LLM prompt formation and event loading."""

from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Query

from app.core.exceptions import LlmProviderUnavailableError
from app.services.gemini_analysis_service import (
    GeminiQuotaExhaustedError,
    GeminiUnavailableError,
)
from app.services.llm_prompt_pipeline_service import get_llm_prompt_pipeline_service

router = APIRouter(prefix="/api/llm-prompt-pipeline", tags=["llm-prompt-pipeline"])


@router.post("/run")
async def run_llm_pipeline(
    provider: Optional[str] = Query(
        None,
        description="AI provider: gemini (2.5 Flash Lite), gemini-flash (2.5 Flash), "
        "gemini-2.5-pro, gemini-2-flash, gemini-3-flash, gemini-3.1-pro, "
        "openai-gpt-5.1, openrouter (deepseek-v4-pro) or local. "
        "Empty or not set — AUTO: tries remote providers in order.",
    ),
    limit: Optional[int] = Query(
        None,
        description="Maximum number of bonds to process. None — all with documents.",
    ),
    rating: Optional[str] = Query(
        None,
        description="Filter by bond credit rating (e.g. AAA, AA+, BBB). "
        "If not set — all floaters with documents are processed.",
    ),
    use_file_upload: bool = Query(
        False,
        description="If True — send original files (PDF, Word) to LLM via Files API; "
        "otherwise — only Markdown text in the prompt.",
    ),
    use_local_events: bool = Query(
        False,
        description="If True — load events from local JSON files "
        "(app/data/events/{INN}.json) instead of e-disclosure.ru.",
    ),
    secid: Optional[str] = Query(
        None,
        description="Specific bond secid to process. If provided, "
        "it will be processed regardless of whether it's already in the database.",
    ),
) -> Dict[str, Any]:
    """Run LLM analysis pipeline for floater bonds with already-downloaded documents.

    Pipeline 2: reads already-existing Markdown files from data/{secid}/,
    loads events (locally or from e-disclosure server), applies existing filters
    (series, regnumber, secid), and sends the prompt to the LLM.

    This pipeline does NOT download any documents — use the emission-doc-download
    pipeline first to prepare the documents.
    """
    try:
        service = get_llm_prompt_pipeline_service()
        return service.run_llm_pipeline(
            provider=provider,
            limit=limit,
            rating=rating,
            use_file_upload=use_file_upload,
            use_local_events=use_local_events,
            secid=secid,
        )
    except GeminiQuotaExhaustedError as exc:
        raise HTTPException(
            status_code=429,
            detail=(
                "Gemini API quota exhausted (429 RESOURCE_EXHAUSTED). "
                "Pipeline stopped. Retry later or check limits in Google AI Studio."
            ),
        ) from exc
    except GeminiUnavailableError as exc:
        raise HTTPException(
            status_code=503,
            detail=(
                "Gemini API temporarily unavailable (503 UNAVAILABLE) after retries. "
                "Pipeline stopped. Retry later."
            ),
        ) from exc
    except LlmProviderUnavailableError as exc:
        raise HTTPException(
            status_code=503,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Error during LLM prompt pipeline: {exc}",
        ) from exc
