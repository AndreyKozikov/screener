"""DTO для ИИ-агента подбора облигаций."""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class AgentSource(BaseModel):
    """Источник данных в ответе агента — конкретная бумага (SECID)."""

    secid: str = Field(description="Код ценной бумаги на MOEX")
    shortname: str = Field(default="", description="Краткое название бумаги")


class AgentTurn(BaseModel):
    """Одна реплика диалога (для истории сессии)."""

    role: str = Field(description='Либо "user", либо "assistant"')
    content: str = Field(description="Текст реплики")
    intent: Optional[str] = Field(
        default=None,
        description="Для ответов агента: ask / tool / answer",
    )
    sources: List[AgentSource] = Field(default_factory=list)


class AgentChatRequest(BaseModel):
    """Запрос пользователя к агенту."""

    query: str = Field(min_length=1, max_length=2000, description="Сообщение пользователя")
    session_id: Optional[str] = Field(default=None, description="Идентификатор диалога")
    history: List[AgentTurn] = Field(
        default_factory=list,
        description="История диалога (используется только при создании новой сессии)",
    )
    portfolio: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Портфель пользователя из localStorage (MVP: только контекст для LLM)",
    )


class AgentChatResponse(BaseModel):
    """Ответ агента пользователю."""

    session_id: str = Field(description="Идентификатор диалога")
    state: str = Field(
        description='Статус: "needs_info" — требуется уточнение, "done" — готовый ответ, "error" — ошибка'
    )
    answer: Optional[str] = Field(default=None, description="Итоговый ответ в Markdown")
    question: Optional[str] = Field(
        default=None,
        description="Уточняющий вопрос агента, когда state == needs_info",
    )
    sources: List[AgentSource] = Field(default_factory=list)
    filters: Optional[Dict[str, Any]] = Field(
        default=None,
        description=(
            "Применённые параметры поиска облигаций (аргументы search_bonds "
            "в каноническом виде, напр. yield_min, rating_min, matdate_from, "
            "bondtype43). Используется фронтендом для ссылки на таблицу рынка."
        ),
    )