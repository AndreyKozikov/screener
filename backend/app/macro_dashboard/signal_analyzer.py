"""Deterministic classifiers for the four macroeconomic directions."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from app.macro_dashboard.calculations import lookup_as_of, signal_from_delta
from app.macro_dashboard.config import ACTIVE_CONFIG, MacroDashboardConfig


def _point_at_latest(series: list[dict[str, Any]]) -> dict[str, Any] | None:
    return next((point for point in reversed(series) if point.get("value") is not None), None)


def _lookback_delta(
    series: list[dict[str, Any]],
    days: int,
    *,
    max_age_days: int | None,
) -> float | None:
    current = _point_at_latest(series)
    if current is None:
        return None
    target = current["_date"] - timedelta(days=days)
    previous = lookup_as_of(series, target, max_age_days=max_age_days)
    return current["value"] - previous["value"] if previous else None


def _make_metric(
    *,
    key: str,
    label: str,
    series: list[dict[str, Any]],
    delta: float | None,
    threshold: float,
    weight: float,
    unit: str = "п.п.",
    delta_90d: float | None = None,
) -> dict[str, Any]:
    latest = _point_at_latest(series)
    return {
        "key": key,
        "label": label,
        "value": latest["value"] if latest else None,
        "date": latest["date"] if latest else None,
        "change": delta,
        "change_90d": delta_90d,
        "unit": unit,
        "threshold": threshold,
        "weight": weight,
        "signal": signal_from_delta(delta, threshold),
    }


class SignalAnalyzer:
    def __init__(self, config: MacroDashboardConfig = ACTIVE_CONFIG) -> None:
        self.config = config

    def analyze(self, calculated: dict[str, Any]) -> list[dict[str, Any]]:
        series = calculated["series"]
        summaries = calculated["summaries"]
        return [
            self._classify(
                "inflation",
                "Инфляция",
                [
                    self._trend_metric(series, summaries, "inflation_mom", "Инфляция за месяц", self.config.inflation_thresholds["inflation_mom"], self.config.inflation_weights["inflation_mom"]),
                    self._trend_metric(series, summaries, "inflation_yoy", "Инфляция за 12 месяцев", self.config.inflation_thresholds["inflation_yoy"], self.config.inflation_weights["inflation_yoy"]),
                    self._trend_metric(series, summaries, "inflation_weekly", "Недельная инфляция", self.config.inflation_thresholds["inflation_weekly"], self.config.inflation_weights["inflation_weekly"]),
                    self._trend_metric(series, summaries, "trend_inflation_3y", "Трендовая инфляция, 3 года", self.config.inflation_thresholds["trend_inflation_3y"], self.config.inflation_weights["trend_inflation_3y"]),
                    self._trend_metric(series, summaries, "trend_inflation_5y", "Трендовая инфляция, 5 лет", self.config.inflation_thresholds["trend_inflation_5y"], self.config.inflation_weights["trend_inflation_5y"]),
                    self._trend_metric(series, summaries, "modified_core_inflation", "Модифицированная базовая инфляция", self.config.inflation_thresholds["modified_core_inflation"], self.config.inflation_weights["modified_core_inflation"]),
                ],
            ),
            self._classify(
                "expectations",
                "Инфляционные ожидания",
                [
                    self._trend_metric(series, summaries, "expectations_1y", "Ожидания на 1 год", self.config.expectations_threshold_pp, self.config.expectations_weights["expectations_1y"]),
                    self._trend_metric(series, summaries, "expectations_5y", "Ожидания на 5 лет", self.config.expectations_threshold_pp, self.config.expectations_weights["expectations_5y"]),
                ],
            ),
            self._classify("monetary_conditions", "Денежно-кредитные условия", self._monetary_metrics(series)),
            self._classify("bond_market", "Рынок ОФЗ", self._market_metrics(series)),
        ]

    @staticmethod
    def _trend_metric(
        series: dict[str, list[dict[str, Any]]],
        summaries: dict[str, dict[str, Any]],
        key: str,
        label: str,
        threshold: float,
        weight: float,
    ) -> dict[str, Any]:
        summary = summaries[key]
        latest = _point_at_latest(series[key])
        return {
            "key": key,
            "label": label,
            "value": summary.get("value"),
            "date": summary.get("date"),
            "change": summary.get("trend_delta"),
            "change_90d": summary.get("change_3m"),
            "unit": "п.п.",
            "threshold": threshold,
            "weight": weight,
            "signal": signal_from_delta(summary.get("trend_delta"), threshold),
            "latest_observation": latest["value"] if latest else None,
        }

    def _monetary_metrics(self, series: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
        ruonia = series["ruonia"]
        key_rate = series["key_rate"]
        spread = series["ruonia_key_rate_spread"]
        ruonia_delta = _lookback_delta(ruonia, 30, max_age_days=10)
        # The official key rate is a step series; an old observation remains effective until changed.
        key_rate_delta = _lookback_delta(key_rate, 30, max_age_days=None)
        spread_delta = _lookback_delta(spread, 30, max_age_days=10)
        return [
            _make_metric(key="ruonia_change_30d", label="Изменение RUONIA за 30 дней", series=ruonia, delta=ruonia_delta, threshold=self.config.monetary_threshold_pp, weight=self.config.monetary_weights["ruonia_change_30d"]),
            _make_metric(key="key_rate_change_30d", label="Изменение ключевой ставки за 30 дней", series=key_rate, delta=key_rate_delta, threshold=self.config.monetary_threshold_pp, weight=self.config.monetary_weights["key_rate_change_30d"]),
            _make_metric(key="spread_change_30d", label="Изменение спреда RUONIA − ключевая за 30 дней", series=spread, delta=spread_delta, threshold=self.config.monetary_threshold_pp, weight=self.config.monetary_weights["spread_change_30d"]),
        ]

    def _market_metrics(self, series: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
        labels = (("term_2_0", "2 года", "yield_2y_change_30d"), ("term_5_0", "5 лет", "yield_5y_change_30d"), ("term_10_0", "10 лет", "yield_10y_change_30d"))
        metrics = []
        for term, label, metric_key in labels:
            points = series[f"yield_{term}"]
            metrics.append(_make_metric(
                key=metric_key,
                label=f"Доходность ОФЗ {label}",
                series=points,
                delta=_lookback_delta(points, 30, max_age_days=14),
                delta_90d=_lookback_delta(points, 90, max_age_days=14),
                threshold=self.config.market_threshold_pp,
                weight=self.config.market_weights[metric_key],
            ))

        two_year = {point["date"]: point for point in series["yield_term_2_0"]}
        ten_year = {point["date"]: point for point in series["yield_term_10_0"]}
        spread_points = []
        for observed_date in sorted(set(two_year) & set(ten_year)):
            short = two_year[observed_date]
            long = ten_year[observed_date]
            if short["value"] is None or long["value"] is None:
                continue
            spread_points.append({
                "date": observed_date,
                "_date": short["_date"],
                "value": long["value"] - short["value"],
            })
        spread_current = _point_at_latest(spread_points)
        metrics.append({
            "key": "yield_spread_10y_2y",
            "label": "Спред доходностей ОФЗ 10Y–2Y",
            "value": spread_current["value"] if spread_current else None,
            "date": spread_current["date"] if spread_current else None,
            "change": _lookback_delta(spread_points, 30, max_age_days=14),
            "change_90d": _lookback_delta(spread_points, 90, max_age_days=14),
            "unit": "п.п.",
            "threshold": self.config.market_threshold_pp,
            "weight": 0,
            "signal": None,
        })
        return metrics

    def _classify(self, key: str, label: str, metrics: list[dict[str, Any]]) -> dict[str, Any]:
        configured_weight = sum(metric["weight"] for metric in metrics)
        available = [metric for metric in metrics if metric.get("signal") is not None and metric["weight"] > 0]
        available_weight = sum(metric["weight"] for metric in available)
        coverage = available_weight / configured_weight if configured_weight else 0
        score = (
            sum(metric["weight"] * metric["signal"] for metric in available) / available_weight
            if available_weight else None
        )
        positive = sum(1 for metric in available if metric["signal"] > 0)
        negative = sum(1 for metric in available if metric["signal"] < 0)
        neutral = sum(1 for metric in available if metric["signal"] == 0)
        positive_weight = sum(metric["weight"] for metric in available if metric["signal"] > 0)
        negative_weight = sum(metric["weight"] for metric in available if metric["signal"] < 0)
        required_coverage = self.config.minimum_coverage[key]

        if coverage < required_coverage or score is None:
            status = "Недостаточно данных"
            trend = "unknown"
            score = None
        else:
            normalized_positive = positive_weight / available_weight
            normalized_negative = negative_weight / available_weight
            is_mixed = (
                normalized_positive >= self.config.mixed_signal_share
                and normalized_negative >= self.config.mixed_signal_share
                and abs(score) < self.config.score_threshold
            )
            if is_mixed:
                status, trend = "Смешанная динамика", "mixed"
            elif score >= self.config.score_threshold:
                status, trend = self._directional_status(key, "up"), "up"
            elif score <= -self.config.score_threshold:
                status, trend = self._directional_status(key, "down"), "down"
            else:
                status, trend = self._directional_status(key, "stable"), "stable"

        return {
            "key": key,
            "name": label,
            "score": score,
            "status": status,
            "trend": trend,
            "positive_count": positive,
            "negative_count": negative,
            "neutral_count": neutral,
            "signal_count": len(available),
            "data_coverage": coverage,
            "available_weight": available_weight,
            "configured_weight": configured_weight,
            "is_available": score is not None,
            "explanation": self._explanation(key, status, len(available), len(metrics)),
            "indicators": metrics,
        }

    @staticmethod
    def _directional_status(key: str, direction: str) -> str:
        status = {
            "inflation": {
                "up": "Инфляционное давление усиливается",
                "down": "Инфляционное давление ослабевает",
                "stable": "Инфляционная динамика стабильна",
            },
            "expectations": {
                "up": "Ожидания растут",
                "down": "Ожидания снижаются",
                "stable": "Ожидания стабильны",
            },
            "monetary_conditions": {
                "up": "Условия ужесточаются",
                "down": "Условия смягчаются",
                "stable": "Существенных изменений нет",
            },
            "bond_market": {
                "up": "Рыночные доходности растут",
                "down": "Рыночные доходности снижаются",
                "stable": "Рыночная динамика стабильна",
            },
        }
        return status[key][direction]

    @staticmethod
    def _explanation(key: str, status: str, available_count: int, total_count: int) -> str:
        if status == "Недостаточно данных":
            return f"Для классификации доступны сигналы {available_count} из {total_count}; покрытия недостаточно."
        reasons = {
            "Инфляционное давление усиливается": "Большинство доступных темпов и оценок устойчивой инфляции ускоряется.",
            "Инфляционное давление ослабевает": "Большинство доступных темпов и оценок устойчивой инфляции замедляется.",
            "Инфляционная динамика стабильна": "В доступных рядах нет значимого изменения средних темпов.",
            "Ожидания растут": "Средние ожидания за последние месяцы выше предыдущего периода.",
            "Ожидания снижаются": "Средние ожидания за последние месяцы ниже предыдущего периода.",
            "Ожидания стабильны": "Доступные ряды ожиданий не показывают значимого изменения.",
            "Условия ужесточаются": "Краткосрочные ставки и их спред в основном растут.",
            "Условия смягчаются": "Краткосрочные ставки и их спред в основном снижаются.",
            "Существенных изменений нет": "Изменения ставок и спреда находятся в пределах заданных порогов.",
            "Рыночные доходности растут": "Большинство доступных доходностей ОФЗ повысилось за 30 дней.",
            "Рыночные доходности снижаются": "Большинство доступных доходностей ОФЗ снизилось за 30 дней.",
            "Рыночная динамика стабильна": "Доходности ОФЗ не изменились значимо по заданным порогам.",
            "Смешанная динамика": "Доступные показатели направления изменяются в разные стороны.",
        }
        return f"{reasons.get(status, 'Оценка построена по доступным показателям.')} Сигналы: {available_count} из {total_count}."
