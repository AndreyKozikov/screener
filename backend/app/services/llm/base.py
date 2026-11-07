from abc import ABC, abstractmethod
from typing import Callable

class BaseLLMProvider(ABC):
    def __init__(self, config):
        self.config = config

    @abstractmethod
    def generate(self, prompt: str, **kwargs) -> str:
        """Отправляет промпт и возвращает полный текст ответа.

        Реализации должны вызывать переданный ``on_chunk`` с каждым текстовым
        фрагментом ответа, если callback задан.
        При ошибках выбрасывает исключение.
        """
        pass
