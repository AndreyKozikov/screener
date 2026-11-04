"""Tunable thresholds and weights for deterministic macro signals."""

from copy import deepcopy
from dataclasses import dataclass, field


@dataclass
class MacroDashboardConfig:
    # Absolute changes are measured in percentage points.
    inflation_thresholds: dict[str, float] = field(default_factory=lambda: {
        "inflation_mom": 0.10,
        "inflation_yoy": 0.15,
        "inflation_weekly": 0.03,
        "trend_inflation_3y": 0.10,
        "trend_inflation_5y": 0.10,
        "modified_core_inflation": 0.10,
    })
    expectations_threshold_pp: float = 0.20
    monetary_threshold_pp: float = 0.10
    market_threshold_pp: float = 0.15

    inflation_weights: dict[str, float] = field(default_factory=lambda: {
        "inflation_mom": 0.25,
        "inflation_yoy": 0.15,
        "inflation_weekly": 0.15,
        "trend_inflation_3y": 0.15,
        "trend_inflation_5y": 0.15,
        "modified_core_inflation": 0.15,
    })
    expectations_weights: dict[str, float] = field(default_factory=lambda: {
        "expectations_1y": 0.60,
        "expectations_5y": 0.40,
    })
    monetary_weights: dict[str, float] = field(default_factory=lambda: {
        "ruonia_change_30d": 0.50,
        "key_rate_change_30d": 0.30,
        "spread_change_30d": 0.20,
    })
    market_weights: dict[str, float] = field(default_factory=lambda: {
        "yield_2y_change_30d": 0.40,
        "yield_5y_change_30d": 0.35,
        "yield_10y_change_30d": 0.25,
    })
    direction_weights: dict[str, float] = field(default_factory=lambda: {
        "inflation": 0.35,
        "expectations": 0.25,
        "monetary_conditions": 0.20,
        "bond_market": 0.20,
    })

    # Minimum share of a direction's configured weight required to classify it.
    minimum_coverage: dict[str, float] = field(default_factory=lambda: {
        "inflation": 0.60,
        "expectations": 0.40,
        "monetary_conditions": 0.50,
        "bond_market": 0.60,
    })
    total_minimum_coverage: float = 0.60
    score_threshold: float = 0.30
    mixed_signal_share: float = 0.20


DEFAULT_CONFIG = MacroDashboardConfig()
ACTIVE_CONFIG = deepcopy(DEFAULT_CONFIG)
