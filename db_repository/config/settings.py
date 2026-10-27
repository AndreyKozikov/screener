"""Settings for the database service boundary."""

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseServiceSettings(BaseSettings):
    api_key: SecretStr = SecretStr("")

    model_config = SettingsConfigDict(
        env_prefix="DB_REPOSITORY_",
        extra="ignore",
    )


settings = DatabaseServiceSettings()
