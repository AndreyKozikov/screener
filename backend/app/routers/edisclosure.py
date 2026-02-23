"""Роутеры для работы с e-disclosure.ru."""

from typing import Dict

from fastapi import APIRouter, HTTPException, Query

from app.services.gemini_analysis_service import (
    GeminiQuotaExhaustedError,
    GeminiUnavailableError,
)
from app.services.edisclosure_service import get_edisclosure_service

router = APIRouter(prefix="/api/edisclosure", tags=["edisclosure"])


@router.get("/accrued-income")
async def get_company_accrued_income(
    secid: str = Query(..., description="Идентификатор ценной бумаги (SECID)"),
    provider: str = Query(
        "gemini",
        description="AI провайдер: gemini (Flash Lite), gemini-flash (2.5 Flash), gemini-3-flash (3 Flash), openai-gpt-5.1 (OpenAI GPT-5.1), openrouter или local",
    ),
) -> Dict[str, str]:
    """Получает и сохраняет параметры флоатера по SECID.

    Вызывает сервисный слой, передавая secid. Сервис скачивает документы,
    анализирует их через Gemini, сохраняет результат в БД и возвращает
    статус выполнения операции.

    Возможные ответы:
    - 200 {"status": "ok"} — анализ выполнен, данные сохранены.
    - 422 {"detail": "..."} — LLM вернул невалидный ответ, данные не сохранены.
    - 404 {"detail": "..."} — облигация или эмитент не найдены в БД.
    - 500 {"detail": "..."} — внутренняя ошибка сервера.
    """
    try:
        service = get_edisclosure_service()
        result: Dict[str, str] = service.get_accrued_income_by_secid(secid, provider=provider)
        if result.get("status") == "error":
            raise HTTPException(
                status_code=422,
                detail=result.get("detail", "Ошибка валидации ответа LLM"),
            )
        return result
    except HTTPException:
        raise
    except GeminiQuotaExhaustedError as exc:
        raise HTTPException(
            status_code=429,
            detail=(
                "Исчерпана квота Gemini API (429). "
                "Повторите запрос позже или проверьте лимиты в Google AI Studio."
            ),
        ) from exc
    except GeminiUnavailableError as exc:
        raise HTTPException(
            status_code=503,
            detail=(
                "Gemini API временно недоступен (503 UNAVAILABLE) после повторов. "
                "Повторите запрос позже."
            ),
        ) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка при получении данных: {exc}",
        ) from exc


@router.post("/update-floaters")
async def update_floaters(
    provider: str = Query(
        "gemini",
        description="AI провайдер: gemini (Flash Lite), gemini-flash (2.5 Flash), gemini-3-flash (3 Flash), openai-gpt-5.1 (OpenAI GPT-5.1), openrouter или local",
    ),
) -> Dict[str, str]:
    """Запускает пакетное обновление данных по всем флоатерам (bond_kind=8).

    При успешном завершении возвращает {"status": "ok"}.
    При исчерпании квоты Gemini API (429) пайплайн останавливается и возвращается 429.
    """
    try:
        service = get_edisclosure_service()
        service.update_all_floaters(provider=provider)
        return {"status": "ok"}
    except GeminiQuotaExhaustedError as exc:
        raise HTTPException(
            status_code=429,
            detail=(
                "Исчерпана квота Gemini API (429 RESOURCE_EXHAUSTED). "
                "Пайплайн остановлен. Повторите запрос позже или проверьте лимиты в Google AI Studio."
            ),
        ) from exc
    except GeminiUnavailableError as exc:
        raise HTTPException(
            status_code=503,
            detail=(
                "Gemini API временно недоступен (503 UNAVAILABLE) после 3 попыток. "
                "Пайплайн остановлен. Повторите запрос позже."
            ),
        ) from exc
