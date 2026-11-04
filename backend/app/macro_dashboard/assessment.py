"""Aggregate direction signals and calculate the weighted argument balance."""

from __future__ import annotations

from app.macro_dashboard.config import ACTIVE_CONFIG, MacroDashboardConfig


class MacroAssessment:
    def __init__(self, config: MacroDashboardConfig = ACTIVE_CONFIG) -> None:
        self.config = config

    def calculate(self, signals: list[dict]) -> dict:
        available = [signal for signal in signals if signal.get("is_available") and signal.get("score") is not None]
        classified_weight = sum(self.config.direction_weights[signal["key"]] for signal in available)
        coverage = classified_weight / sum(self.config.direction_weights.values()) if self.config.direction_weights else 0

        if not available:
            return {
                "index": None,
                "status": "Недостаточно данных",
                "coverage": 0,
                "classified_weight": 0,
                "interpretation": "Недостаточно данных для формирования общей оценки.",
                "balance": [],
                "is_available": False,
                "note": "Индекс и доли сигналов не являются вероятностью решения Банка России.",
            }

        weighted_score = sum(
            self.config.direction_weights[signal["key"]] * signal["score"]
            for signal in available
        ) / classified_weight
        weighted_score = max(-1.0, min(1.0, weighted_score))
        enough_coverage = coverage >= self.config.total_minimum_coverage
        if not enough_coverage:
            index = None
            status = "Недостаточно данных"
            interpretation = "Недостаточно данных для формирования общей оценки."
        else:
            index = weighted_score
            if index <= -self.config.score_threshold:
                status = "Преобладают аргументы за снижение ставки"
                interpretation = "Преобладают дезинфляционные сигналы."
            elif index >= self.config.score_threshold:
                status = "Преобладают аргументы за повышение ставки"
                interpretation = "Преобладают инфляционные риски."
            elif abs(index) < self.config.score_threshold:
                status = "Нет выраженного преобладания"
                interpretation = "Сигналы макроэкономических показателей разнонаправленные или близки к нейтральным."
            else:
                status = "Нет выраженного преобладания"
                interpretation = "Нет выраженного преобладания сигналов."

        categories = {
            "cut": {"key": "cut", "label": "Аргументы за снижение", "count": 0, "weight": 0.0},
            "hold": {"key": "hold", "label": "Аргументы за сохранение", "count": 0, "weight": 0.0},
            "hike": {"key": "hike", "label": "Аргументы за повышение", "count": 0, "weight": 0.0},
        }
        for signal in available:
            score = signal["score"]
            weight = self.config.direction_weights[signal["key"]]
            category = "cut" if score < 0 else "hike" if score > 0 else "hold"
            categories[category]["count"] += 1
            categories[category]["weight"] += weight

        balance = []
        for category in categories.values():
            category["share"] = category["weight"] / classified_weight if classified_weight else 0
            balance.append(category)

        return {
            "index": index,
            "raw_index": weighted_score,
            "status": status,
            "coverage": coverage,
            "classified_weight": classified_weight,
            "interpretation": interpretation,
            "balance": balance,
            "is_available": index is not None,
            "note": "Индекс и доли сигналов не являются вероятностью решения Банка России.",
        }
