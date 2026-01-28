"""Роутеры для работы с историей торгов по облигациям.

Этот модуль содержит роутеры FastAPI для обработки HTTP запросов на скачивание
истории торгов по облигациям с API Мосбиржи. Данные сохраняются в файл
bonds_trading_history.json (ключ — secid).
"""

import asyncio

from fastapi import APIRouter, HTTPException

from app.services.trading_history_service import get_trading_history_service

router = APIRouter(prefix="/api/trading-history", tags=["trading-history"])
"""Роутер FastAPI для обработки запросов к API истории торгов."""




@router.get("/download")
async def download_trading_history():
    """Запускает обновление истории торгов по всем облигациям из bonds.json.
    
    Загружает список облигаций из файла bonds.json и обновляет историю торгов
    для каждой облигации путем загрузки данных с API Мосбиржи. Выполняет
    инкрементальное обновление - загружает только новые данные с последней
    даты в существующих данных до текущей даты.
    
    Returns:
        Словарь с результатами обновления, содержащий:
        - updated: Количество успешно обновленных облигаций
        - failed: Количество облигаций с ошибками при обновлении
        - total: Общее количество облигаций для обработки
        - errors: Список ошибок (если есть)
    
    Raises:
        HTTPException: Если сервис истории торгов не инициализирован (статус 503)
            или если произошла ошибка при обновлении данных (статус 502).
    
    Note:
        Фронтенд не передает никаких параметров - только команду на запуск.
        Список облигаций бэкенд получает из файла bonds.json. Данные сохраняются
        в файл bonds_trading_history.json, где ключ - secid облигации.
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
