"""Ошибки модуля оценки портфеля облигаций."""


class PortfolioValuationError(ValueError):
    """Ошибка входных данных или расчёта оценки портфеля.

    Наследуется от ValueError, чтобы использовать существующую систему
    обработки ошибок проекта. HTTP-статус передаётся в роутер для
    преобразования в HTTPException.
    """

    def __init__(self, message: str, status_code: int = 422) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
