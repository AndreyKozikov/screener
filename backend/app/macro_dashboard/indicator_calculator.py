"""Convert source series into comparable indicators and compact chart payloads."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from app.macro_dashboard.calculations import (
    lookup_as_of,
    monthly_cpi_series,
    normalize_series,
    summarize_series,
    weekly_cpi_series,
)
from app.macro_dashboard.data_provider import MacroRawData


YIELD_TERMS: tuple[tuple[str, str, float], ...] = (
    ("term_0_25", "3 месяца", 0.25),
    ("term_0_5", "6 месяцев", 0.5),
    ("term_0_75", "9 месяцев", 0.75),
    ("term_1_0", "1 год", 1.0),
    ("term_2_0", "2 года", 2.0),
    ("term_3_0", "3 года", 3.0),
    ("term_5_0", "5 лет", 5.0),
    ("term_7_0", "7 лет", 7.0),
    ("term_10_0", "10 лет", 10.0),
    ("term_15_0", "15 лет", 15.0),
    ("term_20_0", "20 лет", 20.0),
    ("term_30_0", "30 лет", 30.0),
)


def _latest_point(series: list[dict[str, Any]]) -> dict[str, Any] | None:
    return next((point for point in reversed(series) if point.get("value") is not None), None)


def _keyrate_at(keyrates: list[dict[str, Any]], target: date) -> float | None:
    point = lookup_as_of(keyrates, target)
    return point.get("value") if point else None


class IndicatorCalculator:
    """Prepare indicator histories once for cards, charts, and signal analysis."""

    def calculate(self, raw: MacroRawData) -> dict[str, Any]:
        monthly_mom, monthly_yoy = monthly_cpi_series(raw.ipc_monthly)
        weekly = weekly_cpi_series(raw.ipc_weekly)
        expectations_actual = normalize_series(
            raw.expectations,
            date_keys=("recorddata", "record_date", "date"),
            value_keys=("observed_annual_inflation",),
        )
        expectations_1y = normalize_series(
            raw.expectations,
            date_keys=("recorddata", "record_date", "date"),
            value_keys=("expected_annual_inflation",),
        )
        expectations_5y = normalize_series(
            raw.expectations,
            date_keys=("recorddata", "record_date", "date"),
            value_keys=("expected_five_year_inflation",),
        )
        trend_3y = normalize_series(
            raw.sustainable_inflation,
            date_keys=("record_date", "recorddata", "date"),
            value_keys=("trend_inflation_3y",),
        )
        trend_5y = normalize_series(
            raw.sustainable_inflation,
            date_keys=("record_date", "recorddata", "date"),
            value_keys=("trend_inflation_5y",),
        )
        modified_core = normalize_series(
            raw.sustainable_inflation,
            date_keys=("record_date", "recorddata", "date"),
            value_keys=("modified_core_inflation",),
        )
        keyrates = normalize_series(
            raw.keyrates,
            date_keys=("dt", "date", "Дата"),
            value_keys=("rate", "Ключевая ставка, % годовых"),
        )
        ruonia = normalize_series(
            raw.ruonia,
            date_keys=("date_stavki", "dt", "date", "Дата ставки"),
            value_keys=("stavka_ruonia", "rate", "Ставка RUONIA, % годовых"),
        )
        yield_series: dict[str, list[dict[str, Any]]] = {}
        for field, _label, _term in YIELD_TERMS:
            yield_series[field] = normalize_series(
                raw.yield_curve,
                date_keys=("date", "Дата"),
                value_keys=(field,),
            )

        # RUONIA's spread is computed against the official rate effective on each observation date.
        spread: list[dict[str, Any]] = []
        for point in ruonia:
            current_date = point["_date"]
            effective_keyrate = _keyrate_at(keyrates, current_date)
            spread.append({
                "date": point["date"],
                "_date": current_date,
                "value": point["value"] - effective_keyrate
                if point["value"] is not None and effective_keyrate is not None else None,
            })

        summaries = {
            "inflation_mom": summarize_series(monthly_mom, frequency="monthly"),
            "inflation_yoy": summarize_series(monthly_yoy, frequency="monthly"),
            "inflation_weekly": summarize_series(weekly, frequency="weekly"),
            "expectations_actual_yoy": summarize_series(expectations_actual, frequency="monthly"),
            "expectations_1y": summarize_series(expectations_1y, frequency="monthly"),
            "expectations_5y": summarize_series(expectations_5y, frequency="monthly"),
            "trend_inflation_3y": summarize_series(trend_3y, frequency="monthly"),
            "trend_inflation_5y": summarize_series(trend_5y, frequency="monthly"),
            "modified_core_inflation": summarize_series(modified_core, frequency="monthly"),
            "key_rate": summarize_series(keyrates, frequency="event"),
            "ruonia": summarize_series(ruonia, frequency="daily"),
            "ruonia_key_rate_spread": summarize_series(spread, frequency="daily"),
        }
        for field, _label, _term in YIELD_TERMS:
            summaries[f"yield_{field}"] = summarize_series(yield_series[field], frequency="daily")

        dashboard_indicators = self._build_dashboard_indicators(summaries, keyrates, ruonia, spread)
        charts = self._build_charts(
            monthly_mom, monthly_yoy, expectations_actual, expectations_1y, expectations_5y,
            keyrates, ruonia, yield_series,
        )

        return {
            "series": {
                "inflation_mom": monthly_mom,
                "inflation_yoy": monthly_yoy,
                "inflation_weekly": weekly,
                "expectations_actual_yoy": expectations_actual,
                "expectations_1y": expectations_1y,
                "expectations_5y": expectations_5y,
                "trend_inflation_3y": trend_3y,
                "trend_inflation_5y": trend_5y,
                "modified_core_inflation": modified_core,
                "key_rate": keyrates,
                "ruonia": ruonia,
                "ruonia_key_rate_spread": spread,
                **{f"yield_{key}": value for key, value in yield_series.items()},
            },
            "summaries": summaries,
            "metrics": dashboard_indicators,
            "charts": charts,
        }

    def _build_dashboard_indicators(
        self,
        summaries: dict[str, dict[str, Any]],
        keyrates: list[dict[str, Any]],
        ruonia: list[dict[str, Any]],
        spread: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        key_rate = summaries["key_rate"]
        ruonia_summary = summaries["ruonia"]
        spread_latest = _latest_point(spread)
        keyrate_latest = _latest_point(keyrates)
        keyrate_previous = keyrates[-2] if len(keyrates) > 1 else None
        key_rate_change = (
            keyrate_latest["value"] - keyrate_previous["value"]
            if keyrate_latest and keyrate_previous and keyrate_latest["value"] is not None and keyrate_previous["value"] is not None
            else None
        )
        ruonia_latest = _latest_point(ruonia)
        spread_value = spread_latest["value"] if spread_latest else None

        definitions = [
            ("key_rate", "Ключевая ставка", key_rate.get("value"), key_rate.get("date"), key_rate_change, "п.п.", "нейтральный"),
            ("inflation_yoy", "Инфляция за 12 месяцев", summaries["inflation_yoy"].get("value"), summaries["inflation_yoy"].get("date"), summaries["inflation_yoy"].get("change"), "п.п.", _inflation_tone(summaries["inflation_yoy"].get("change"))),
            ("inflation_mom", "Инфляция за месяц", summaries["inflation_mom"].get("value"), summaries["inflation_mom"].get("date"), summaries["inflation_mom"].get("change"), "п.п.", _inflation_tone(summaries["inflation_mom"].get("change"))),
            ("expectations_1y", "Ожидания инфляции, 1 год", summaries["expectations_1y"].get("value"), summaries["expectations_1y"].get("date"), summaries["expectations_1y"].get("change"), "п.п.", _inflation_tone(summaries["expectations_1y"].get("change"))),
            ("modified_core_inflation", "Устойчивая инфляция", summaries["modified_core_inflation"].get("value"), summaries["modified_core_inflation"].get("date"), summaries["modified_core_inflation"].get("change"), "п.п.", _inflation_tone(summaries["modified_core_inflation"].get("change"))),
            ("ruonia", "RUONIA", ruonia_summary.get("value"), ruonia_summary.get("date"), spread_value, "п.п. к ключевой ставке", "нейтральный"),
        ]
        indicators: list[dict[str, Any]] = []
        change_labels = {
            "key_rate": "к предыдущему решению",
            "ruonia": "спред RUONIA − ключевая ставка",
        }
        for key, label, value, observed_date, change, unit, tone in definitions:
            indicators.append({
                "key": key,
                "label": label,
                "value": value,
                "unit": "%",
                "date": observed_date,
                "change": change,
                "change_unit": unit,
                "change_label": change_labels.get(key, "к предыдущему месяцу"),
                "tone": tone,
            })
        if indicators[-1]["date"] is None and ruonia_latest:
            indicators[-1]["date"] = ruonia_latest["date"]
        if indicators[0]["date"] is None and keyrate_latest:
            indicators[0]["date"] = keyrate_latest["date"]
        if spread_value is None:
            indicators[-1]["change"] = None
        return indicators

    def _build_charts(
        self,
        monthly_mom: list[dict[str, Any]],
        monthly_yoy: list[dict[str, Any]],
        expectations_actual: list[dict[str, Any]],
        expectations_1y: list[dict[str, Any]],
        expectations_5y: list[dict[str, Any]],
        keyrates: list[dict[str, Any]],
        ruonia: list[dict[str, Any]],
        yield_series: dict[str, list[dict[str, Any]]],
    ) -> dict[str, Any]:
        by_month_yoy = {point["date"]: point["value"] for point in monthly_yoy}
        inflation_points = [
            {"date": point["date"], "mom": point["value"], "yoy": by_month_yoy.get(point["date"])}
            for point in monthly_mom
        ]

        expectation_maps = [
            {point["date"]: point["value"] for point in series}
            for series in (expectations_actual, expectations_1y, expectations_5y)
        ]
        expectation_dates = sorted(set().union(*(set(points) for points in expectation_maps)))
        expectations_points = [
            {
                "date": observed_date,
                "actual_yoy": expectation_maps[0].get(observed_date),
                "expected_1y": expectation_maps[1].get(observed_date),
                "expected_5y": expectation_maps[2].get(observed_date),
            }
            for observed_date in expectation_dates
        ]
        expectation_gaps = {
            "one_year": _latest_gap(expectations_1y, expectations_actual),
            "five_year": _latest_gap(expectations_5y, expectations_actual),
        }

        monetary_points = []
        for point in ruonia:
            key_rate = _keyrate_at(keyrates, point["_date"])
            monetary_points.append({"date": point["date"], "ruonia": point["value"], "key_rate": key_rate})

        curve_dates = sorted({
            point["_date"]
            for series in yield_series.values()
            for point in series
        })
        curve_latest_date = curve_dates[-1] if curve_dates else None
        curve_old_target = curve_latest_date - timedelta(days=30) if curve_latest_date else None
        curve_old_date = max(
            (observed_date for observed_date in curve_dates if curve_old_target and observed_date <= curve_old_target),
            default=None,
        )
        if curve_old_date and curve_old_target and (curve_old_target - curve_old_date).days > 14:
            curve_old_date = None
        curve_current: dict[str, dict[str, Any]] = {}
        curve_previous: dict[str, dict[str, Any]] = {}
        curve_rows_by_date: dict[date, dict[str, dict[str, Any]]] = {}
        for key, series in yield_series.items():
            for point in series:
                curve_rows_by_date.setdefault(point["_date"], {})[key] = point
        if curve_latest_date is not None:
            for key, series in yield_series.items():
                curve_current[key] = next((point for point in reversed(series) if point["_date"] == curve_latest_date), None)  # type: ignore[assignment]
                curve_previous[key] = next((point for point in reversed(series) if curve_old_date and point["_date"] == curve_old_date), None)  # type: ignore[assignment]

        curve_history = [
            {
                "date": observed_date.isoformat(),
                "data": [
                    {
                        "term": key,
                        "maturity": label,
                        "years": years,
                        "value": curve_rows_by_date.get(observed_date, {}).get(key, {}).get("value"),
                    }
                    for key, label, years in YIELD_TERMS
                ],
            }
            for observed_date in curve_dates
        ]

        curve_points: list[dict[str, Any]] = []
        for key, label, years in YIELD_TERMS:
            current = curve_current.get(key)
            previous = curve_previous.get(key)
            current_value = current.get("value") if current else None
            previous_value = previous.get("value") if previous else None
            curve_points.append({
                "term": key,
                "maturity": label,
                "years": years,
                "current": current_value,
                "previous": previous_value,
                "change": current_value - previous_value if current_value is not None and previous_value is not None else None,
            })

        return {
            "inflation": inflation_points,
            "expectations": expectations_points,
            "expectation_gaps": expectation_gaps,
            "monetary_conditions": monetary_points,
            "yield_curve": {
                "date": curve_latest_date.isoformat() if curve_latest_date else None,
                "comparison_date": curve_old_date.isoformat() if curve_old_date else None,
                "data": curve_points,
                "history": curve_history,
            },
        }


def _inflation_tone(change: float | None) -> str:
    if change is None or abs(change) < 0.005:
        return "нейтральный"
    return "дезинфляционный" if change < 0 else "инфляционный"


def _latest_gap(
    expectation: list[dict[str, Any]],
    actual: list[dict[str, Any]],
) -> dict[str, Any]:
    actual_by_date = {point["date"]: point["value"] for point in actual}
    for point in reversed(expectation):
        observed = actual_by_date.get(point["date"])
        if point["value"] is not None and observed is not None:
            return {"value": point["value"] - observed, "date": point["date"]}
    return {"value": None, "date": None}
