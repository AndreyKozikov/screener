from pathlib import Path
from typing import Any, List

from pydantic import field_validator
from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from conversion_service.config.config_loader import env_is_set, load_config

# Путь к .env — корень conversion_service
_SERVICE_DIR = Path(__file__).resolve().parent.parent
_env_file_path = None
if (_SERVICE_DIR / ".env").exists():
    _env_file_path = str(_SERVICE_DIR / ".env")


def _load_auth_secret_key() -> str:
    """Read the shared token signing key from conversion_service/.env.

    backend/.env используется как fallback только если файл существует:
    при совместной работе значения AUTH_SECRET_KEY в обоих сервисах должны совпадать.
    """
    candidates = [
        _SERVICE_DIR / ".env",
        _SERVICE_DIR.parent / "backend" / ".env",
    ]
    for candidate in candidates:
        if not candidate.exists():
            continue
        for line in candidate.read_text(encoding="utf-8").splitlines():
            key, separator, value = line.partition("=")
            if separator and key.strip() == "AUTH_SECRET_KEY":
                return value.strip().strip("\"'")
    return ""


class Settings(BaseSettings):
    """Настройки приложения Conversion Service."""

    API_V1_STR: str = "/api"
    PROJECT_NAME: str = "Conversion Service API"

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

    PDF2MD_BASE_URL: str = "http://localhost:9000"
    DB_REPOSITORY_URL: str = "http://127.0.0.1:8964"
    DB_REPOSITORY_API_KEY: SecretStr = SecretStr("")
    DB_REPOSITORY_TIMEOUT_SECONDS: float = 300.0
    DB_REPOSITORY_CONNECT_TIMEOUT_SECONDS: float = 10.0
    DB_REPOSITORY_VERIFY_TLS: bool = True
    DB_REPOSITORY_CA_BUNDLE: str = ""
    DB_REPOSITORY_MAX_RETRIES: int = 0
    DATA_DIR: str = "../backend/app/data"
    EMITENT_EVENTS_JSON_DIR: str = "../backend/app/data/events"
    AUTH_SECRET_KEY: SecretStr = SecretStr(_load_auth_secret_key())
    LOCAL_LLM_BASE_URL: str = "http://127.0.0.1:7000"
    LOCAL_LLM_GENERATE_PATH: str = "/api/v1/llm/generate"
    LOCAL_LLM_ANALYSIS_MAX_NEW_TOKENS: int = 1024
    LOCAL_LLM_ANALYSIS_TEMPERATURE: float = 0.1
    LOCAL_LLM_ANALYSIS_TOP_P: float = 0.9

    model_config = SettingsConfigDict(
        env_file=_env_file_path,
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
        env_ignore_empty=True,
    )

    def model_post_init(self, __context: Any) -> None:
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
            "EMITENT_EVENTS_JSON_DIR": paths.get("emitent_events_json_dir"),
        }
        for field_name, value in defaults.items():
            if value is not None and not env_is_set(field_name):
                setattr(self, field_name, value)


settings = Settings()
