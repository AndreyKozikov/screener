from typing import Type

from app.services.llm.base import BaseLLMProvider


# type -> класс провайдера
PROVIDER_REGISTRY: dict[str, Type[BaseLLMProvider]] = {}


def register_provider(
    provider_type: str,
    provider_cls: Type[BaseLLMProvider],
) -> None:
    """
    Регистрирует реализацию провайдера.
    """
    PROVIDER_REGISTRY[provider_type] = provider_cls


def get_provider_class(
    provider_type: str,
) -> Type[BaseLLMProvider] | None:
    """
    Возвращает класс провайдера по его типу.
    """
    return PROVIDER_REGISTRY.get(provider_type)