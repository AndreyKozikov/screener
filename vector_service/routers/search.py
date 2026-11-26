from fastapi import APIRouter, Header, Request, Response

from ..http_utils import authorized, error
from ..models.api import SearchRequest, SearchResult
from ..services.document_index import InvalidSearch

router = APIRouter()


@router.post("/search", response_model=SearchResult, responses={202: {"model": SearchResult}})
def search(payload: SearchRequest, request: Request, response: Response, x_api_key: str = Header(default="")):
    if not authorized(request, x_api_key):
        return error(401, "unauthorized", "Неверный ключ доступа")
    try:
        result = request.app.state.index.search(payload)
    except InvalidSearch as exc:
        return error(409, "provider_mismatch", str(exc))
    if result.status == "not_indexed":
        response.status_code = 202
    return result
