"""Схемы DTO для пайплайна получения параметров флоатеров из эмиссионных документов через LLM."""

from typing import Optional
from pydantic import BaseModel, Field


class FloatParamsAnalizeLLM(BaseModel):
    """DTO для запуска пайплайна получения параметров флоатеров через LLM."""

    provider: Optional[str] = Field(
        None,
        description=(
            "AI provider: gemini (2.5 Flash Lite), gemini-flash (2.5 Flash), "
            "gemini-2.5-pro, gemini-2-flash, gemini-3-flash, gemini-3.1-pro, "
            "openai-gpt-5.1, openrouter (deepseek-v4-pro) or local. "
            "Empty or not set — AUTO: tries remote providers in order."
        ),
    )
    limit: Optional[int] = Field(
        None,
        description="Maximum number of bonds to process. None — all with documents.",
    )
    rating: Optional[str] = Field(
        None,
        description=(
            "Filter by bond credit rating (e.g. AAA, AA+, BBB). "
            "If not set — all floaters with documents are processed."
        ),
    )
    use_local_events: bool = Field(
        True,
        description=(
            "If True — load events from local JSON files "
            "(app/data/events/{INN}.json) instead of e-disclosure.ru."
        ),
    )
    secid: Optional[str] = Field(
        None,
        description=(
            "Specific bond secid to process. If provided, "
            "it will be processed regardless of whether it's already in the database."
        ),
    )
    embedding_model: Optional[str] = Field(
        None,
        description=(
            "Embedding model for vector retrieval: local (default) or "
            "openrouter-bge-m3."
        ),
    )
