"""Глобальные обработчики исключений для приложения BondsScreener."""

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

# Импортируем классы ошибок из твоего файла exceptions.py
from app.core.exceptions import (
    PromptTooLongError,
    GeminiQuotaExhaustedError,
    GeminiUnavailableError,
    LlmProviderUnavailableError,
)


def register_pipeline_exception_handlers(fastapi_app: FastAPI) -> None:
    """Регистрирует все глобальные обработчики исключений в приложении."""

    @fastapi_app.exception_handler(LlmProviderUnavailableError)
    async def llm_provider_handler(request: Request, exc: LlmProviderUnavailableError):
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"detail": str(exc)},
        )

    @fastapi_app.exception_handler(PromptTooLongError)
    async def prompt_too_long_handler(request: Request, exc: PromptTooLongError):
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "detail": exc.message,
                "length": exc.length,
                "limit": exc.limit,
            },
        )

    @fastapi_app.exception_handler(GeminiQuotaExhaustedError)
    async def gemini_quota_handler(request: Request, exc: GeminiQuotaExhaustedError):
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={
                "detail": (
                    "Gemini API quota exhausted (429 RESOURCE_EXHAUSTED). "
                    "Pipeline stopped. Retry later or check limits in Google AI Studio."
                )
            },
        )

    @fastapi_app.exception_handler(GeminiUnavailableError)
    async def gemini_unavailable_handler(request: Request, exc: GeminiUnavailableError):
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "detail": (
                    "Gemini API temporarily unavailable (503 UNAVAILABLE) after retries. "
                    "Pipeline stopped. Retry later."
                )
            },
        )

    @fastapi_app.exception_handler(ValueError)
    async def value_error_handler(request: Request, exc: ValueError):
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"detail": str(exc)},
        )
