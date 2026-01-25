"""
Эндпоинт скачивания истории торгов по облигациям с API Мосбиржи.
Данные сохраняются в backend/app/data/bonds_trading_history.json (ключ — secid).

Фронтенд даёт только команду на запуск; список облигаций бэкенд получает из bonds.json.
"""

import asyncio

from fastapi import APIRouter, HTTPException

from app.services.trading_history_service import get_trading_history_service

router = APIRouter(prefix="/api/trading-history", tags=["trading-history"])


@router.get("/download")
async def download_trading_history():
    """
    Запускает обновление истории торгов по всем облигациям из bonds.json.

    Список облигаций бэкенд получает из файла с данными. Фронтенд не передаёт
    никаких параметров — только команду на запуск.

    Возвращает: updated, failed, total, errors.
    """
    try:
        svc = get_trading_history_service()
    except RuntimeError as e:
        raise HTTPException(
            status_code=503,
            detail="Сервис истории торгов не инициализирован.",
        ) from e
    try:
        result = await asyncio.to_thread(svc.download_history_all)
        return result
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e)) from e
