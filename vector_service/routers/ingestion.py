from fastapi import APIRouter, Header, Request

from ..http_utils import authorized, error
from ..models.api import IngestRequest, IngestResult
from ..services.document_index import InvalidCatalog

router = APIRouter(prefix="/index", tags=["Индексация"])


@router.post("/events", response_model=IngestResult)
def index_events(payload: IngestRequest, request: Request, x_api_key: str = Header(default="")):
    """Обрабатывает переданные выпуски и события и возвращает итог записи."""
    if not authorized(request, x_api_key):
        return error(401, "unauthorized", "Неверный ключ доступа")
    try:
        return request.app.state.index.ingest(payload)
    except InvalidCatalog as exc:
        return error(400, "invalid_catalog", str(exc))
