from openai import OpenAI

from app.services.llm.base import BaseLLMProvider
from app.services.llm.registry import register_provider


class OpenRouterProvider(BaseLLMProvider):
    def __init__(self, config, api_key: str):
        super().__init__(config)
        self.api_key = api_key
        self.model = config.model
        self._client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=api_key,
        )

    def generate(self, prompt: str, **kwargs) -> str:
        temperature = kwargs.get("temperature", 0.1)
        on_chunk = kwargs.get("on_chunk")
        system_instruction = kwargs.get("system_instruction")
        messages = []
        if system_instruction:
            messages.append({"role": "system", "content": system_instruction})
        messages.append({"role": "user", "content": prompt})

        if on_chunk is None:
            completion = self._client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
            )
            return completion.choices[0].message.content or ""

        chunks = []
        stream = self._client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
            stream=True,
        )
        for item in stream:
            if not item.choices:
                continue
            content = item.choices[0].delta.content
            if isinstance(content, str) and content:
                chunks.append(content)
                on_chunk(content)
            elif isinstance(content, list):
                for part in content:
                    text = getattr(part, "text", None)
                    if text:
                        chunks.append(text)
                        on_chunk(text)
        return "".join(chunks)


register_provider("openrouter", OpenRouterProvider)
