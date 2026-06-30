"""Domain-specific exceptions for the BondsScreener application."""

from typing import Optional

class LlmProviderUnavailableError(Exception):
    """Raised when no remote LLM provider passes availability probe in auto mode."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message: str = message


class PromptTooLongError(Exception):
    """Raised when the prepared LLM prompt exceeds the allowed character limit."""

    def __init__(self, message: str, length: int, limit: int) -> None:
        super().__init__(message)
        self.message: str = message
        self.length: int = length
        self.limit: int = limit


class GeminiQuotaExhaustedError(Exception):
    """Raised when Gemini API quota is exhausted (429)."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message: str = message


class GeminiUnavailableError(Exception):
    """Raised when Gemini API is temporarily unavailable (503)."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message: str = message