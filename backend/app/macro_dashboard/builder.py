"""Orchestrate collection, indicator preparation, and assessment for the API."""

from __future__ import annotations

from datetime import datetime, timezone

from app.macro_dashboard.assessment import MacroAssessment
from app.macro_dashboard.data_provider import DataProvider
from app.macro_dashboard.indicator_calculator import IndicatorCalculator
from app.macro_dashboard.signal_analyzer import SignalAnalyzer


class DashboardDataBuilder:
    def __init__(
        self,
        data_provider: DataProvider | None = None,
        indicator_calculator: IndicatorCalculator | None = None,
        signal_analyzer: SignalAnalyzer | None = None,
        macro_assessment: MacroAssessment | None = None,
    ) -> None:
        self.data_provider = data_provider or DataProvider()
        self.indicator_calculator = indicator_calculator or IndicatorCalculator()
        self.signal_analyzer = signal_analyzer or SignalAnalyzer()
        self.macro_assessment = macro_assessment or MacroAssessment()

    async def build(self) -> dict:
        raw = await self.data_provider.fetch()
        calculated = self.indicator_calculator.calculate(raw)
        signals = self.signal_analyzer.analyze(calculated)
        assessment = self.macro_assessment.calculate(signals)

        source_counts = {
            "keyrate": len(raw.keyrates),
            "ruonia": len(raw.ruonia),
            "ipc_monthly": len(raw.ipc_monthly),
            "ipc_weekly": len(raw.ipc_weekly),
            "expectations": len(raw.expectations),
            "sustainable_inflation": len(raw.sustainable_inflation),
            "yield_curve": len(raw.yield_curve),
        }
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "dashboard_indicators": calculated["metrics"],
            "dashboard_charts": calculated["charts"],
            "macro_signals": signals,
            "macro_assessment": assessment,
            "indicator_calculations": calculated["summaries"],
            "data_quality": {
                "source_counts": source_counts,
                "source_errors": raw.errors,
                "warnings": [
                    f"Источник «{name}» недоступен: {message}"
                    for name, message in raw.errors.items()
                ],
            },
        }
