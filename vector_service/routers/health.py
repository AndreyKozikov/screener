import logging

from fastapi import APIRouter, Request

from ..http_utils import error

router = APIRouter()


@router.get("/health")
def health():
    return {"status": "ok"}


@router.get("/ready")
def ready(request: Request):
    try:
        if request.app.state.index.ready():
            return {"status": "ok"}
    except (ValueError, RuntimeError, OSError):
        logging.exception("Ошибка проверки готовности поиска")
    return error(503, "degraded", "Хранилище или модель не готовы к поиску")
