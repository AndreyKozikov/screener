"""Роутер ИИ-агента подбора облигаций.

Регистрируется в main.py условно (settings.AGENT_ENABLED), чтобы фичу можно
было мгновенно отключить без правок кода.
"""

from fastapi import APIRouter, Depends, HTTPException

from app.agent.dto import AgentChatRequest, AgentChatResponse
from app.agent.service import get_agent_service
from app.agent.chat_repository import repository as chat_repository
from app.routers.auth import get_current_user

router = APIRouter(prefix="/api/agent", tags=["agent"])


@router.post("/chat", response_model=AgentChatResponse)
async def agent_chat(payload: AgentChatRequest, user: dict = Depends(get_current_user)) -> AgentChatResponse:
    """Принимает сообщение пользователя и возвращает ответ ИИ-агента.

    Ответ может быть:
    - state=needs_info: агент задаёт уточняющий вопрос (question);
    - state=done: итоговый ответ (answer, Markdown) + источники (sources);
    - state=error: сообщение об ошибке (answer).
    """
    service = get_agent_service()
    try:
        return await service.chat(payload, str(user["id"]))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/chats")
def list_chats(user: dict = Depends(get_current_user)) -> list[dict]:
    return chat_repository.list_chats(str(user["id"]))


@router.get("/chats/{session_id}")
def get_chat(session_id: str, user: dict = Depends(get_current_user)) -> dict:
    chat = chat_repository.get_chat(str(user["id"]), session_id)
    if chat is None:
        raise HTTPException(status_code=404, detail="Чат не найден")
    return chat


@router.delete("/chats/{session_id}")
def delete_chat(session_id: str, user: dict = Depends(get_current_user)) -> dict:
    if not chat_repository.delete_chat(str(user["id"]), session_id):
        raise HTTPException(status_code=404, detail="Чат не найден")
    return {"deleted": True}
