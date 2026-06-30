from app.services.llm.registry import get_provider_class
from config.settings import settings
from app.core.exceptions import LlmProviderUnavailableError


class LlmProviderFactory:
    @staticmethod
    def create(provider_config):
        provider_cls = get_provider_class(provider_config.type)
        if provider_cls is None:
            raise ValueError(f"Неизвестный тип провайдера: {provider_config.type}")

        api_key_var = f"{provider_config.type.upper()}_API_KEY"
        api_key = getattr(settings, api_key_var, None)
        if api_key is None:
            raise LlmProviderUnavailableError(
                f"API key for {provider_config.type} not configured in settings"
            )
        extra = {}
        extra["api_key"] = api_key

        return provider_cls(provider_config, **extra)