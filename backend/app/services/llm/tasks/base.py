from abc import ABC, abstractmethod
from typing import Any, Dict

class BaseAnalysisTask(ABC):
    """Базовый класс для всех типов задач, отправляемых в LLM (Паттерн Стратегия)."""

    @abstractmethod
    def build_prompt(self, data: Dict[str, Any]) -> str:
        """Формирует и возвращает итоговый текст промпта для LLM."""
        pass

    @abstractmethod
    def parse_response_and_validate(self, raw_text: str, **kwargs) -> Any:
        """Парсит сырой текстовый ответ от LLM и превращает его в DTO или структуру."""
        pass