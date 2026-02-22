"""Роутеры для работы с e-disclosure.ru."""

from typing import Dict

from fastapi import APIRouter, HTTPException, Query

from app.services.edisclosure_service import get_edisclosure_service

router = APIRouter(prefix="/api/edisclosure", tags=["edisclosure"])


@router.get("/accrued-income")
async def get_company_accrued_income(
    secid: str = Query(..., description="Идентификатор ценной бумаги (SECID)"),
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
        result: Dict[str, str] = service.get_accrued_income_by_secid(secid)
        if result.get("status") == "error":
            raise HTTPException(
                status_code=422,
                detail=result.get("detail", "Ошибка валидации ответа LLM"),
            )
        return result
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка при получении данных: {exc}",
        ) from exc
