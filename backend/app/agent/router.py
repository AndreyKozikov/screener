"""Роутер ИИ-агента подбора облигаций.

Регистрируется в main.py условно (settings.AGENT_ENABLED), чтобы фичу можно
было мгновенно отключить без правок кода.
"""

from fastapi import APIRouter

from app.agent.dto import AgentChatRequest, AgentChatResponse
from app.agent.service import get_agent_service

router = APIRouter(prefix="/api/agent", tags=["agent"])


@router.post("/chat", response_model=AgentChatResponse)
async def agent_chat(payload: AgentChatRequest) -> AgentChatResponse:
    """Принимает сообщение пользователя и возвращает ответ ИИ-агента.

    Ответ может быть:
    - state=needs_info: агент задаёт уточняющий вопрос (question);
    - state=done: итоговый ответ (answer, Markdown) + источники (sources);
    - state=error: сообщение об ошибке (answer).
    """
    service = get_agent_service()
    return await service.chat(payload)