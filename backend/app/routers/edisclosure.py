"""Роутеры для работы с e-disclosure.ru."""

from fastapi import APIRouter, HTTPException, Query

from app.services.edisclosure_service import get_edisclosure_service

router = APIRouter(prefix="/api/edisclosure", tags=["edisclosure"])


@router.get("/accrued-income")
async def get_company_accrued_income(
    secid: str = Query(..., description="Идентификатор ценной бумаги (SECID)"),
):
    """Получает данные начисленных доходов по SECID облигации.

    Вызывает сервисный слой, передавая secid.
    """
    try:
        service = get_edisclosure_service()
        result = service.get_accrued_income_by_secid(secid)
        return result
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка при получении данных: {exc}",
        ) from exc
