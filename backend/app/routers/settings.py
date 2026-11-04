"""Роутер runtime-настроек приложения.

GET  /api/settings — возвращает описание всех настраиваемых параметров
                     (вкладки, поля, типы, текущие значения и значения по умолчанию).
PUT  /api/settings — применяет и сохраняет переопределения (или сбрасывает все).
"""

from typing import Any, Dict

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services import runtime_settings_service

router = APIRouter(prefix="/api", tags=["settings"])


class SettingsUpdateRequest(BaseModel):
    """Запрос на обновление runtime-настроек.

    Attributes:
        reset_all: если True, все переопределения сбрасываются к конфигурации по умолчанию.
        updates: словарь «ключ настройки → новое значение». Пустое значение
            для секретных полей означает «не менять».
    """
    reset_all: bool = Field(default=False, description="Сбросить все настройки к умолчаниям")
    updates: Dict[str, Any] = Field(default_factory=dict, description="Переопределения настроек")


@router.get("/settings")
async def get_settings() -> Dict[str, Any]:
    """Возвращает схему настроек для страницы настроек фронтенда."""
    return runtime_settings_service.get_schema()


@router.put("/settings")
async def update_settings(request: SettingsUpdateRequest) -> Dict[str, Any]:
    """Применяет переопределения (или сбрасывает) и возвращает обновлённую схему."""
    try:
        if request.reset_all:
            runtime_settings_service.reset_runtime_settings()
        else:
            runtime_settings_service.update_runtime_settings(request.updates)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Не удалось обновить настройки: {exc}")
    return runtime_settings_service.get_schema()