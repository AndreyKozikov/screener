import tomllib
from pathlib import Path

from pydantic import Field, PositiveInt, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="VECTOR_", env_file=ROOT / ".env", extra="ignore")
    service_api_key: SecretStr = Field(min_length=1)
    model_dir: Path
    db_dir: Path = ROOT / "data/lancedb"
    embedding_dim: PositiveInt = 1024
    model_id: str = "baai/bge-m3"
    sparse_source: str = "bge-m3-service"
    gc_timeout: PositiveInt = 300

    @classmethod
    def settings_customise_sources(cls, settings_cls, init_settings, env_settings, dotenv_settings, file_secret_settings):
        def toml_settings():
            path = ROOT / "config/config.toml"
            if path.is_file():
                with path.open("rb") as source:
                    return tomllib.load(source).get("vector", {})
            return {}
        return init_settings, env_settings, dotenv_settings, toml_settings, file_secret_settings


class OpenRouterSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="OPENROUTER_", env_file=ROOT / ".env", extra="ignore")
    api_key: SecretStr = Field(min_length=1)
    http_referer: str | None = None
    x_title: str | None = None
