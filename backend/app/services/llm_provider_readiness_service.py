"""Сервис проверки готовности и выбора доступного LLM-провайдера.

Модуль обеспечивает автоматический подбор работающего API-ключа и доступной модели
перед запуском ресурсоемких процессов анализа документации.
"""

from typing import List, Optional, Tuple

from app.core.exceptions import LlmProviderUnavailableError
from app.services.gemini_analysis_service import (
    GEMINI_MODEL_2_5_PRO,
    GEMINI_MODEL_2_FLASH,
    GEMINI_MODEL_3_1_PRO,
    GEMINI_MODEL_3_FLASH,
    GEMINI_MODEL_FLASH,
    GEMINI_MODEL_FLASH_LITE,
    GeminiClient,
    GeminiQuotaExhaustedError,
    GeminiUnavailableError,
)
from app.services.openai_analysis_service import OpenAIClient
from app.services.openrouter_analysis_service import OpenRouterClient
from config.settings import settings

_PROBE_PROMPT: str = "Reply with exactly one word: OK"

# Порядок как в EdisclosureService / роутере; local исключён из AUTO.
_AUTO_REMOTE_PROVIDER_ORDER: Tuple[str, ...] = (
    "gemini",
    "gemini-flash",
    "gemini-2.5-pro",
    "gemini-2-flash",
    "gemini-3-flash",
    "gemini-3.1-pro",
    "openai-gpt-5.1",
    "openrouter",
)


def _gemini_model_id_for_provider(provider: str) -> Optional[str]:
    """Идентификатор модели Gemini для имени провайдера или None (не Gemini)."""
    if provider == "gemini":
        return GEMINI_MODEL_FLASH_LITE
    if provider == "gemini-flash":
        return GEMINI_MODEL_FLASH
    if provider == "gemini-2.5-pro":
        return GEMINI_MODEL_2_5_PRO
    if provider == "gemini-2-flash":
        return GEMINI_MODEL_2_FLASH
    if provider == "gemini-3-flash":
        return GEMINI_MODEL_3_FLASH
    if provider == "gemini-3.1-pro":
        return GEMINI_MODEL_3_1_PRO
    return None


class LlmProviderReadinessService:
    """Сервис динамического выбора поставщика LLM.

    Позволяет системе автоматически переключаться между различными провайдерами
    (Gemini, OpenAI, OpenRouter) в случае исчерпания квот или недоступности API.
    """

    def resolve_provider(self, explicit_provider: Optional[str]) -> str:
        """Возвращает имя провайдера для пайплайна.

        - None или пустая строка (после strip): AUTO — перебор удалённых провайдеров с пробой.
        - Явный ``local`` (без учёта регистра): ``local`` без пробы.
        - Иной непустой явный параметр: возвращается без пробы (нормализация в lower).

        Raises:
            LlmProviderUnavailableError: В режиме AUTO ни один удалённый провайдер не прошёл пробу.
        """
        raw: str = (explicit_provider or "").strip()
        if not raw:
            return self._resolve_auto_remote()
        if raw.lower() == "local":
            print(
                "[LLM-PROBE] explicit provider=local — пропуск проверки, используется локальная LLM",
                flush=True,
            )
            return "local"
        resolved: str = raw.lower()
        print(
            f"[LLM-PROBE] explicit provider={resolved!r} — пропуск проверки (режим не AUTO)",
            flush=True,
        )
        return resolved

    def _resolve_auto_remote(self) -> str:
        print("[LLM-PROBE] режим AUTO: перебор удалённых провайдеров с минимальной пробой", flush=True)
        attempted: List[str] = []
        for name in _AUTO_REMOTE_PROVIDER_ORDER:
            attempted.append(name)
            gemini_model: Optional[str] = _gemini_model_id_for_provider(name)
            if gemini_model is not None:
                key: str = (settings.GEMINI_API_KEY or "").strip()
                if not key:
                    print(
                        f"[LLM-PROBE] provider={name!r}: пропуск — нет GEMINI_API_KEY",
                        flush=True,
                    )
                    continue
                print(
                    f"[LLM-PROBE] проба Gemini: provider={name!r}, model={gemini_model!r}",
                    flush=True,
                )
                try:
                    client: GeminiClient = GeminiClient(api_key=key)
                    _ = client.generate(_PROBE_PROMPT, model=gemini_model)
                    print(
                        f"[LLM-PROBE] успех: provider={name!r} (Gemini, model={gemini_model!r})",
                        flush=True,
                    )
                    return name
                except GeminiQuotaExhaustedError as exc:
                    print(
                        f"[LLM-PROBE] provider={name!r}: квота/лимит (GeminiQuotaExhaustedError): {exc}",
                        flush=True,
                    )
                    continue
                except GeminiUnavailableError as exc:
                    print(
                        f"[LLM-PROBE] provider={name!r}: недоступен (GeminiUnavailableError): {exc}",
                        flush=True,
                    )
                    continue
                except Exception as exc:
                    print(
                        f"[LLM-PROBE] provider={name!r}: ошибка пробы Gemini: {exc}",
                        flush=True,
                    )
                    continue

            if name == "openai-gpt-5.1":
                oa_key: str = (settings.OPENAI_API_KEY or "").strip()
                if not oa_key:
                    print(
                        "[LLM-PROBE] provider=openai-gpt-5.1: пропуск — нет OPENAI_API_KEY",
                        flush=True,
                    )
                    continue
                print("[LLM-PROBE] проба OpenAI (gpt-5.1)", flush=True)
                try:
                    oa_client: OpenAIClient = OpenAIClient(api_key=oa_key)
                    _ = oa_client.generate(_PROBE_PROMPT)
                    print("[LLM-PROBE] успех: provider=openai-gpt-5.1 (OpenAI)", flush=True)
                    return "openai-gpt-5.1"
                except GeminiQuotaExhaustedError as exc:
                    print(
                        f"[LLM-PROBE] provider=openai-gpt-5.1: квота/лимит: {exc}",
                        flush=True,
                    )
                    continue
                except GeminiUnavailableError as exc:
                    print(
                        f"[LLM-PROBE] provider=openai-gpt-5.1: недоступен: {exc}",
                        flush=True,
                    )
                    continue
                except Exception as exc:
                    print(
                        f"[LLM-PROBE] provider=openai-gpt-5.1: ошибка пробы: {exc}",
                        flush=True,
                    )
                    continue

            if name == "openrouter":
                or_key: str = (settings.OPENROUTER_API_KEY or "").strip()
                if not or_key:
                    print(
                        "[LLM-PROBE] provider=openrouter: пропуск — нет OPENROUTER_API_KEY",
                        flush=True,
                    )
                    continue
                print("[LLM-PROBE] проба OpenRouter", flush=True)
                try:
                    or_client: OpenRouterClient = OpenRouterClient(api_key=or_key)
                    _ = or_client.generate(_PROBE_PROMPT)
                    print("[LLM-PROBE] успех: provider=openrouter", flush=True)
                    return "openrouter"
                except Exception as exc:
                    print(
                        f"[LLM-PROBE] provider=openrouter: ошибка пробы: {exc}",
                        flush=True,
                    )
                    continue

            print(
                f"[LLM-PROBE] provider={name!r}: неизвестный тип — пропуск",
                flush=True,
            )

        detail: str = (
            "Ни один удалённый LLM-провайдер не прошёл проверку доступности (AUTO). "
            f"Проверены: {', '.join(attempted)}"
        )
        print(f"[LLM-PROBE] {detail}", flush=True)
        raise LlmProviderUnavailableError(detail)
