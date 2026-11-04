"""Пакет ИИ-агента подбора облигаций.

Полностью изолирован от основных сервисов: агент читает данные через их
публичные функции (get_bonds_list, get_bond_detail и т.д.) как обычный
внешний вызывающий. Подключение роутера управляется фиче-флагом
settings.AGENT_ENABLED в main.py.
"""

from app.agent.dto import (
    AgentChatRequest,
    AgentChatResponse,
    AgentSource,
    AgentTurn,
)
from app.agent.service import AgentService, get_agent_service

__all__ = [
    "AgentChatRequest",
    "AgentChatResponse",
    "AgentSource",
    "AgentTurn",
    "AgentService",
    "get_agent_service",
]