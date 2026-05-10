"""Роутеры для работы с e-disclosure.ru."""

from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Query

from app.services.gemini_analysis_service import (
    GeminiQuotaExhaustedError,
    GeminiUnavailableError,
)
from app.core.exceptions import LlmProviderUnavailableError
from app.services.edisclosure_service import get_edisclosure_service

router = APIRouter(prefix="/api/edisclosure", tags=["edisclosure"])


@router.get("/accrued-income")
async def get_company_accrued_income(
    secid: str = Query(..., description="Идентификатор ценной бумаги (SECID)"),
    provider: Optional[str] = Query(
        None,
        description="AI провайдер: gemini (2.5 Flash Lite), gemini-flash (2.5 Flash), gemini-2.5-pro, gemini-2-flash, gemini-3-flash, gemini-3.1-pro, openai-gpt-5.1, openrouter или local. Не передавать или пусто — AUTO: проба удалённых провайдеров по очереди.",
    ),
    use_file_upload: bool = Query(
        False,
        description="Если True — в LLM (Gemini/OpenAI) подавать оригинальные файлы (PDF, Word) через Files API; по умолчанию — только текст Markdown в промпте.",
    ),
    use_local_events: bool = Query(
        False,
        description="Если True — события берутся из локальных JSON-файлов "
        "(app/data/events/{ИНН}.json) вместо запросов к e-disclosure.ru.",
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
        result: Dict[str, str] = service.get_accrued_income_by_secid(
            secid, provider=provider, use_file_upload=use_file_upload,
            use_local_events=use_local_events,
        )
        if result.get("status") == "error":
            raise HTTPException(
                status_code=422,
                detail=result.get("detail", "Ошибка валидации ответа LLM"),
            )
        return result
    except HTTPException:
        raise
    except GeminiQuotaExhaustedError as exc:
        provider_name: str = "Gemini API"
        provider_limits_hint: str = "или проверьте лимиты в Google AI Studio."
        raise HTTPException(
            status_code=429,
            detail=(
                f"Исчерпана квота {provider_name} (429). "
                f"Повторите запрос позже {provider_limits_hint}"
            ),
        ) from exc
    except GeminiUnavailableError as exc:
        provider_name = "Gemini API"
        raise HTTPException(
            status_code=503,
            detail=(
                f"{provider_name} временно недоступен (503 UNAVAILABLE) после повторов. "
                "Повторите запрос позже."
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
            detail=f"Ошибка при получении данных: {exc}",
        ) from exc


@router.post("/update-floaters")
async def update_floaters(
    provider: Optional[str] = Query(
        None,
        description="AI провайдер: gemini (2.5 Flash Lite), gemini-flash (2.5 Flash), gemini-2.5-pro, gemini-2-flash, gemini-3-flash, gemini-3.1-pro, openai-gpt-5.1, openrouter или local. Не передавать или пусто — AUTO: проба удалённых провайдеров по очереди.",
    ),
    limit: Optional[int] = Query(
        None,
        description="Количество облигаций для обновления. По умолчанию — все, у которых нет данных.",
    ),
    use_file_upload: bool = Query(
        False,
        description="Если True — в LLM (Gemini/OpenAI) подавать оригинальные файлы (PDF, Word) через Files API; по умолчанию — только текст Markdown в промпте.",
    ),
    rating: Optional[str] = Query(
        None,
        description="Фильтр по рейтингу облигаций (например AAA, AA+, BBB). Если не задан — обрабатываются все флоатеры.",
    ),
    use_local_events: bool = Query(
        False,
        description="Если True — события берутся из локальных JSON-файлов "
        "(app/data/events/{ИНН}.json) вместо запросов к e-disclosure.ru.",
    ),
) -> Dict[str, str]:
    """Запускает пакетное обновление данных по всем флоатерам (bond_kind=8).

    При успешном завершении возвращает {"status": "ok"}.
    При исчерпании квоты Gemini API (429) пайплайн останавливается и возвращается 429.
    """
    try:
        service = get_edisclosure_service()
        service.update_all_floaters(
            provider=provider, limit=limit, use_file_upload=use_file_upload,
            rating=rating, use_local_events=use_local_events,
        )
        return {"status": "ok"}
    except GeminiQuotaExhaustedError as exc:
        provider_name: str = "Gemini API"
        provider_limits_hint: str = "или проверьте лимиты в Google AI Studio."
        raise HTTPException(
            status_code=429,
            detail=(
                f"Исчерпана квота {provider_name} (429 RESOURCE_EXHAUSTED). "
                f"Пайплайн остановлен. Повторите запрос позже {provider_limits_hint}"
            ),
        ) from exc
    except GeminiUnavailableError as exc:
        provider_name = "Gemini API"
        raise HTTPException(
            status_code=503,
            detail=(
                f"{provider_name} временно недоступен (503 UNAVAILABLE) после 3 попыток. "
                "Пайплайн остановлен. Повторите запрос позже."
            ),
        ) from exc
    except LlmProviderUnavailableError as exc:
        raise HTTPException(
            status_code=503,
            detail=str(exc),
        ) from exc


@router.post("/fetch-emission-documents")
async def fetch_emission_documents(
    limit: Optional[int] = Query(
        None,
        description="Количество эмитентов для обработки. По умолчанию — все.",
    ),
) -> Dict[str, Any]:
    """Скачивает эмиссионные документы эмитентов с e-disclosure.ru.

    Для каждого эмитента из emitent_edisclosure загружает HTML-страницу
    эмиссионных документов, парсит таблицу и сохраняет записи в БД.
    Приоритет: сначала эмитенты без документов в таблице.

    Args:
        limit: Количество эмитентов для обработки. None — все.

    Returns:
        JSON со статистикой: processed, total_docs_added, empty_count.
    """
    try:
        service = get_edisclosure_service()
        return service.fetch_emission_documents(limit=limit)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка при скачивании эмиссионных документов: {exc}",
        ) from exc


@router.post("/populate-emitent-edisclosure")
async def populate_emitent_edisclosure_endpoint() -> Dict[str, int]:
    """Заполняет таблицу соответствия id эмитента (MOEX) и id на e-disclosure.ru.

    Для каждого эмитента с непустым ИНН из таблицы emitents выполняет поиск
    компании на e-disclosure.ru по ИНН и сохраняет edisclosure_id в таблицу
    emitent_edisclosure через репозиторий. Эмитенты, уже в таблице, пропускаются.

    Returns:
        Статистика: total_emitents, already_in_table, to_process, saved, skipped.
    """
    service = get_edisclosure_service()
    return service.populate_emitent_edisclosure()
