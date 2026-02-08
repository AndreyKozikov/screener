"""DTO для отдачи на главную страницу: курсы валют, ставка RUONIA и ключевая ставка.

Используется одним эндпоинтом для быстрой загрузки плашки с макро-показателями
без множественных запросов. Фронтенд отображает данные без преобразований.
"""

from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, Field


class CurrencyRateItem(BaseModel):
    """Один курс валюты для отображения в плашке.

    Attributes:
        code: Код валюты (EUR, USD, CNY).
        rate: Курс за 1 единицу валюты в рублях.
        nominal: Номинал (опционально).
        original_value: Исходное значение из API (опционально).
    """

    model_config = ConfigDict(populate_by_name=True)

    code: str = Field(description="Код валюты")
    rate: float = Field(description="Курс за 1 ед. в рублях")
    nominal: int = Field(default=1, description="Номинал валюты")
    original_value: str = Field(default="", description="Исходное значение из API ЦБ РФ")


class MacroRatesDTO(BaseModel):
    """Данные для плашки на главной: курсы валют, RUONIA и ключевая ставка.

    Один ответ эндпоинта содержит все показатели для быстрого запуска.
    Фронтенд использует поля как есть, без преобразований.

    Attributes:
        date: Дата курсов валют (YYYY-MM-DD).
        source_date: Дата из ответа API ЦБ РФ.
        rates: Словарь курсов валют: ключ — код (EUR, USD, CNY), значение — CurrencyRateItem.
        ruonia_rate: Текущая ставка RUONIA, % годовых, или None.
        key_rate: Текущая ключевая ставка ЦБ, % годовых, или None.
    """

    model_config = ConfigDict(populate_by_name=True)

    date: str = Field(description="Дата курсов валют (YYYY-MM-DD)")
    source_date: str = Field(default="", description="Дата из API ЦБ РФ")
    rates: Dict[str, CurrencyRateItem] = Field(
        default_factory=dict,
        description="Курсы валют: EUR, USD, CNY",
    )
    ruonia_rate: Optional[float] = Field(
        default=None,
        description="Ставка RUONIA, % годовых",
    )
    key_rate: Optional[float] = Field(
        default=None,
        description="Ключевая ставка ЦБ РФ, % годовых",
    )

    @classmethod
    def from_services(
        cls,
        currency_dict: Dict[str, Any],
        ruonia_rate_value: Optional[float],
        key_rate_value: Optional[float],
    ) -> "MacroRatesDTO":
        """Собирает DTO из результатов сервисов (для использования в сервисном слое).

        Args:
            currency_dict: Словарь от currency_service.get_rates (date, source_date, rates).
            ruonia_rate_value: Значение ставки RUONIA или None.
            key_rate_value: Значение ключевой ставки или None.

        Returns:
            Экземпляр MacroRatesDTO.
        """
        rates = {}
        for code, item in (currency_dict.get("rates") or {}).items():
            if isinstance(item, dict) and "rate" in item:
                rates[code] = CurrencyRateItem(
                    code=item.get("code", code),
                    rate=float(item["rate"]),
                    nominal=int(item.get("nominal", 1)),
                    original_value=str(item.get("original_value", "")),
                )
        return cls(
            date=currency_dict.get("date", ""),
            source_date=currency_dict.get("source_date", ""),
            rates=rates,
            ruonia_rate=ruonia_rate_value,
            key_rate=key_rate_value,
        )
