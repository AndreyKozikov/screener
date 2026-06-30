"""Сервис проверки готовности и выбора доступного LLM-провайдера.

Модуль обеспечивает автоматический подбор работающего API-ключа и доступной модели
перед запуском ресурсоемких процессов анализа документации.
"""

from typing import List, Optional

from app.core.exceptions import LlmProviderUnavailableError

from app.services.llm.factory import LlmProviderFactory
from config.settings import settings

_PROBE_PROMPT: str = "Reply with exactly one word: OK"


class LlmProviderResolutionService:
    """Сервис динамического выбора поставщика LLM.

    Позволяет системе автоматически переключаться между различными провайдерами
    (Gemini, OpenAI, OpenRouter) в случае исчерпания квот или недоступности API.
    """

    def resolve_provider(self, explicit_provider: Optional[str]) -> str:
        """Возвращает имя провайдера для пайплайна.

        - None или пустая строка (после strip): AUTO — перебор удалённых провайдеров с пробой.
        - Явный ``local`` (без учёта регистра): ``local`` без пробы.
        - Иной непустой явный параметр: возвращается без пробы (нормализация в lower).

        """
        raw: str = (explicit_provider or "").strip().lower()
        if not raw:
            return self._resolve_auto_remote()
        if raw == "local":
            return "local"
        return raw

    def _resolve_auto_remote(self) -> str:
        print("[LLM-PROBE] режим AUTO: перебор удалённых провайдеров с минимальной пробой", flush=True)
        attempted: List[str] = []
        providers = settings.llm.remote_providers

        for name in providers:
            attempted.append(name)
            provider_config = settings.llm.providers.get(name)
            if provider_config is None:
                print(f"[LLM-PROBE] provider={name!r}: нет конфигурации", flush=True)
                continue

            print(f"[LLM-PROBE] проба {provider_config.type}: provider={name!r}, model={provider_config.model!r}",
                  flush=True)

            try:
                provider = LlmProviderFactory.create(provider_config)
                provider.generate(_PROBE_PROMPT)
                print(f"[LLM-PROBE] успех: provider={name!r} (model={provider_config.model!r})", flush=True)
                return name
            except Exception as exc:
                print(f"[LLM-PROBE] provider={name!r}: ошибка пробы: {exc}", flush=True)
                continue

        detail: str = (
            "Ни один удалённый LLM-провайдер не прошёл проверку доступности (AUTO). "
            f"Проверены: {', '.join(attempted)}"
        )
        print(f"[LLM-PROBE] {detail}", flush=True)
        raise LlmProviderUnavailableError(detail)


_llm_provider_resolution_service: Optional[LlmProviderResolutionService] = None


def init_llm_provider_resolution_service() -> None:
    global _llm_provider_resolution_service
    _llm_provider_resolution_service = LlmProviderResolutionService()


def get_llm_provider_resolution_service() -> LlmProviderResolutionService:
    if _llm_provider_resolution_service is None:
        raise RuntimeError("LLMProviderResolutionService not initialized. "
                           "Call init_llm_provider_resolution_service first.")
    return _llm_provider_resolution_service
