from abc import ABC, abstractmethod

class BaseLLMProvider(ABC):
    def __init__(self, config):
        self.config = config

    @abstractmethod
    def generate(self, prompt: str, **kwargs) -> str:
        """Отправляет промт модели и возвращает текст ответа.
        При ошибках выбрасывает исключение.
        """
        pass