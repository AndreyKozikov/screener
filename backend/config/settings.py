"""Настройки приложения (Pydantic Settings).

Загружаются из .env и переменных окружения. Путь к .env берётся из config.paths.
"""

import tomllib
from pydantic import BaseModel, SecretStr
from pathlib import Path
from typing import Any, List

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from config.config_loader import env_is_set, load_config

# Путь к .env — корень backend (родитель папки config)
_BACKEND_DIR = Path(__file__).resolve().parent.parent
_env_file_path = None
if (_BACKEND_DIR / ".env").exists():
    _env_file_path = str(_BACKEND_DIR / ".env")


def _load_auth_secret_key() -> str:
    """Read the signing key from its single source: backend/.env."""
    if _env_file_path is None:
        return ""
    for line in Path(_env_file_path).read_text(encoding="utf-8").splitlines():
        key, separator, value = line.partition("=")
        if separator and key.strip() == "AUTH_SECRET_KEY":
            return value.strip().strip("\"'")
    return ""

_CONFIG_LLM_PATH = _BACKEND_DIR / "config" / "config_llm.toml"

class ProviderConfig(BaseModel):
    model: str
    type: str


class LlmConfig(BaseModel):
    probe_prompt: str
    remote_providers: list[str]
    providers: dict[str, ProviderConfig]

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

    llm: LlmConfig | None = None

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: Any) -> Any:
        if isinstance(v, str):
            if v.strip() == "*":
                return ["*"]
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v

    DATA_DIR: str = "./data"

    DB_REPOSITORY_URL: str = "http://127.0.0.1:8964"
    DB_REPOSITORY_API_KEY: SecretStr = SecretStr("")
    DB_REPOSITORY_TIMEOUT_SECONDS: float = 300.0
    DB_REPOSITORY_CONNECT_TIMEOUT_SECONDS: float = 10.0
    DB_REPOSITORY_VERIFY_TLS: bool = True
    DB_REPOSITORY_CA_BUNDLE: str = ""
    DB_REPOSITORY_MAX_RETRIES: int = 0
    CONVERSION_SERVICE_URL: str = "http://127.0.0.1:12345/api"
    AUTH_SECRET_KEY: SecretStr = SecretStr(_load_auth_secret_key())
    AUTH_TOKEN_TTL_HOURS: int = 168

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

    # ИИ-агент подбора облигаций. agent_enabled=False полностью отключает
    # регистрацию роутера /api/agent/chat без правок кода.
    AGENT_ENABLED: bool = True
    # Имя LLM-провайдера из config_llm.toml (например "gemini-flash");
    # пустая строка = AUTO (перебор доступных провайдеров с пробой).
    AGENT_PROVIDER: str = ""
    # Логирование сессий агента: каждый новый диалог пишется в отдельную
    # папку с запросами/уточнениями пользователя и JSON-ответами модели.
    AGENT_LOG_ENABLED: bool = True
    AGENT_LOG_DIR: str = "logs/agent_sessions"

    def model_post_init(self, __context: Any) -> None:
        self._load_llm_config()
        self._load_service_config()

    def _load_llm_config(self) -> None:
        if _CONFIG_LLM_PATH.exists():
            with open(_CONFIG_LLM_PATH, "rb") as f:
                data = tomllib.load(f)

            llm_data = data.get("llm")
            if llm_data:
                self.llm = LlmConfig.model_validate(llm_data)

    def _load_service_config(self) -> None:
        """Применить несекретные значения из config/config.toml.

        Переменные окружения имеют приоритет над TOML. Секреты в TOML
        не хранятся и не читаются.
        """
        config = load_config()
        db_repository = config.get("db_repository", {})
        paths = config.get("paths", {})

        defaults = {
            "DB_REPOSITORY_URL": db_repository.get("url"),
            "DB_REPOSITORY_TIMEOUT_SECONDS": db_repository.get("timeout_seconds"),
            "DB_REPOSITORY_CONNECT_TIMEOUT_SECONDS": db_repository.get("connect_timeout_seconds"),
            "DB_REPOSITORY_VERIFY_TLS": db_repository.get("verify_tls"),
            "DB_REPOSITORY_CA_BUNDLE": db_repository.get("ca_bundle"),
            "DB_REPOSITORY_MAX_RETRIES": db_repository.get("max_retries"),
            "DATA_DIR": paths.get("data_dir"),
        }
        for field_name, value in defaults.items():
            if value is not None and not env_is_set(field_name):
                setattr(self, field_name, value)

    model_config = SettingsConfigDict(
        env_file=_env_file_path,
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
        env_ignore_empty=True,
    )

settings = Settings()
