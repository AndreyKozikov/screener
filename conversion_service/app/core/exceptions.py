"""Domain-specific exceptions for the BondsScreener application."""

from typing import Optional


class PdfConversionConnectionError(Exception):
    """
    Raised when the pdf2md batch conversion fails due to a connection or HTTP error.

    Typical causes: remote host forcibly closed the connection (e.g. WinError 10054),
    connection reset, timeout, or other network/HTTP errors from the pdf2md service.
    """

    def __init__(self, message: str, cause: Optional[BaseException] = None) -> None:
        super().__init__(message)
        self.message = message
        self.cause = cause


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
