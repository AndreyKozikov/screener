from google.genai.errors import APIError
from app.core.exceptions import GeminiQuotaExhaustedError, GeminiUnavailableError
import logging
from google import genai
from google.genai import types

from app.services.llm.base import BaseLLMProvider
from app.services.llm.registry import register_provider


logger = logging.getLogger(__name__)


class GeminiProvider(BaseLLMProvider):
    """Провайдер для Google Gemini API."""

    def __init__(self, config, api_key: str):
        super().__init__(config)
        self.api_key = api_key
        self.model = config.model
        self._client = genai.Client(api_key=api_key)

    def generate(self, prompt: str, **kwargs) -> str | None:
        system_instruction = kwargs.get("system_instruction")
        on_chunk = kwargs.get("on_chunk")
        config = types.GenerateContentConfig(temperature=0.1)
        if system_instruction:
            config.system_instruction = system_instruction

        try:
            if on_chunk is not None:
                chunks = []
                stream = self._client.models.generate_content_stream(
                    model=self.model,
                    contents=prompt,
                    config=config,
                )
                for chunk in stream:
                    try:
                        text = chunk.text
                    except (AttributeError, ValueError):
                        text = None
                    if text:
                        chunks.append(text)
                        on_chunk(text)
                return "".join(chunks)

            response = self._client.models.generate_content(
                model=self.model,
                contents=prompt,
                config=config,
            )
            return response.text
        except APIError as exc:
            if exc.code == 429:
                raise GeminiQuotaExhaustedError(str(exc)) from exc
            elif exc.code == 503:
                raise GeminiUnavailableError(str(exc)) from exc
            raise exc

register_provider("gemini", GeminiProvider)
