"""Настройки приложения (Pydantic Settings).

Загружаются из .env и переменных окружения. Путь к .env берётся из config.paths.
"""

from pathlib import Path
from typing import Any, List

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Путь к .env — корень backend (родитель папки config)
_BACKEND_DIR = Path(__file__).resolve().parent.parent
_env_file_path = None
if (_BACKEND_DIR / ".env").exists():
    _env_file_path = str(_BACKEND_DIR / ".env")


class Settings(BaseSettings):
    """Настройки приложения BondsScreener."""

    API_V1_STR: str = "/api"
    PROJECT_NAME: str = "Bonds Screener API"

    CORS_ORIGINS: List[str] | str = [
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000",
    ]

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: Any) -> Any:
        if isinstance(v, str):
            if v.strip() == "*":
                return ["*"]
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v

    DATA_DIR: str = "./data"

    MOEX_BONDS_URL: str = (
        "https://iss.moex.com/iss/engines/stock/markets/bonds/securities.json"
    )

    PDF2MD_BASE_URL: str = "http://localhost:9000"

    OPENAI_API_KEY: str = ""
    GEMINI_API_KEY: str = ""
    OPENROUTER_API_KEY: str = ""
    OPENROUTER_HTTP_REFERER: str = ""
    OPENROUTER_X_TITLE: str = ""

    LOCAL_LLM_BASE_URL: str = "http://127.0.0.1:7000"
    LOCAL_LLM_GENERATE_PATH: str = "/api/v1/llm/generate"
    LOCAL_LLM_ANALYSIS_MAX_NEW_TOKENS: int = 1024
    LOCAL_LLM_ANALYSIS_TEMPERATURE: float = 0.1
    LOCAL_LLM_ANALYSIS_TOP_P: float = 0.9

    FLOATER_ANALYSIS_PROMPT_MAX_CHARS: int = 980000

    model_config = SettingsConfigDict(
        env_file=_env_file_path,
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
        env_ignore_empty=True,
    )


settings = Settings()
