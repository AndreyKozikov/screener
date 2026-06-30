import logging
from openai import OpenAI
from app.services.llm.base import BaseLLMProvider
from app.services.llm.registry import register_provider

logger = logging.getLogger(__name__)


class OpenAIProvider(BaseLLMProvider):
    def __init__(self, config, api_key: str):
        super().__init__(config)
        self.api_key = api_key
        self.model = config.model
        self._client = OpenAI(api_key=api_key)

    def generate(self, prompt: str, **kwargs) -> str:
        temperature = kwargs.get("temperature", 0.1)
        completion = self._client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
        )
        return completion.choices[0].message.content


register_provider("openai", OpenAIProvider)