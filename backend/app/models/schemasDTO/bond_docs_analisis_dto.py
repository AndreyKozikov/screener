from typing import Optional
from pydantic import BaseModel, Field


class BondBondsDocsAnalisisDTO(BaseModel):
    secid: str = Field(
        ...,
        description="SECID облигации"
    )

    regnumber: Optional[str] = Field(
        None,
        description="Регистрационный номер (опционально)"
    )
    use_local_events: bool = Field(
        True,
        description="Использовать локальный кэш событий"
    )

    query: Optional[str] = Field(
        None,
        description="Пользовательский запрос для поиска"
    )

    provider: Optional[str] = Field(
        None,
        description=(
            "AI provider: gemini (2.5 Flash Lite), gemini-flash (2.5 Flash), "
            "gemini-2.5-pro, gemini-2-flash, gemini-3-flash, gemini-3.1-pro, "
            "openai-gpt-5.1, openrouter (deepseek-v4-pro) or local. "
            "Empty or not set — AUTO: tries remote providers in order."
        )
    )
    embedding_model: Optional[str] = Field(
        None,
        description="Тип модели эмбеддингов: local или openrouter-bge-m3",
    )
