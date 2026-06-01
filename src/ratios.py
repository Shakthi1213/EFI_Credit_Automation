"""
ratios.py
---------
Ratio calculation engine for NBFC credit intelligence.

The public function returns structured calculation metadata while preserving
top-level ratio fields for the existing dashboard and scoring engine.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

import numpy as np
import pandas as pd


RATIO_FIELDS = {
    "roa",
    "roe",
    "debt_equity",
    "interest_coverage",
    "gnpa_pct",
    "nnpa_pct",
    "leverage_ratio",
    "liquidity_ratio",
}


@dataclass(frozen=True)
class RatioDefinition:
    key: str
    label: str
    inputs: tuple[str, ...]
    calculator: Callable[[dict[str, Any]], float | None]
    category: str


def calculate_ratios(data: dict[str, Any]) -> dict[str, Any]:
    """
    Calculate core NBFC credit ratios from mapped financial data.

    Missing or zero denominators return None. Existing ratio values are kept
    intact and are not overwritten.
    """
    if not isinstance(data, dict):
        raise TypeError("calculate_ratios expects a dictionary input.")

    normalized_data = {key: _to_number(value) for key, value in data.items()}
    enriched_data = dict(data)
    calculated_ratios: dict[str, float | None] = {}
    missing_inputs: list[dict[str, Any]] = []
    calculation_details: dict[str, dict[str, Any]] = {}

    for definition in _ratio_definitions():
        existing_value = _to_number(data.get(definition.key))
        if existing_value is not None:
            value = _round_ratio(existing_value)
            source = "provided"
            missing_for_ratio: list[str] = []
        else:
            missing_for_ratio = _missing_inputs(normalized_data, definition.inputs)
            value = None if missing_for_ratio else definition.calculator(normalized_data)
            value = _round_ratio(value)
            source = "calculated" if value is not None else "unavailable"

        calculated_ratios[definition.key] = value
        enriched_data[definition.key] = value
        calculation_details[definition.key] = {
            "label": definition.label,
            "category": definition.category,
            "inputs": list(definition.inputs),
            "source": source,
            "value": value,
        }

        if value is None:
            missing_inputs.append(
                {
                    "ratio": definition.key,
                    "required_inputs": list(definition.inputs),
                    "missing_inputs": missing_for_ratio,
                }
            )

    possible = len(RATIO_FIELDS)
    successful = sum(value is not None for value in calculated_ratios.values())
    calculation_confidence = round(successful / possible, 2) if possible else 0.0

    enriched_data.update(
        {
            "calculated_ratios": calculated_ratios,
            "missing_inputs": missing_inputs,
            "calculation_confidence": calculation_confidence,
            "calculation_details": calculation_details,
            "regulatory_readiness": {
                "supported_future_checks": [
                    "car_thresholds",
                    "leverage_thresholds",
                    "gnpa_stress_bands",
                    "liquidity_monitoring",
                    "sma_warning_logic",
                    "concentration_monitoring",
                ]
            },
            "benchmarking_readiness": {
                "comparison_dimensions": [
                    "company_ratios",
                    "peer_averages",
                    "industry_medians",
                    "percentile_rankings",
                ]
            },
        }
    )
    return enriched_data


def _ratio_definitions() -> tuple[RatioDefinition, ...]:
    return (
        RatioDefinition(
            key="roa",
            label="ROA (%)",
            inputs=("pat", "total_assets"),
            calculator=lambda d: _percentage(d.get("pat"), d.get("total_assets")),
            category="profitability",
        ),
        RatioDefinition(
            key="roe",
            label="ROE (%)",
            inputs=("pat", "net_worth"),
            calculator=lambda d: _percentage(d.get("pat"), d.get("net_worth")),
            category="profitability",
        ),
        RatioDefinition(
            key="debt_equity",
            label="Debt-to-Equity (x)",
            inputs=("total_debt", "net_worth"),
            calculator=lambda d: safe_divide(d.get("total_debt"), d.get("net_worth")),
            category="leverage",
        ),
        RatioDefinition(
            key="interest_coverage",
            label="Interest Coverage (x)",
            inputs=("ebit", "interest_expense"),
            calculator=lambda d: safe_divide(d.get("ebit"), d.get("interest_expense")),
            category="coverage",
        ),
        RatioDefinition(
            key="gnpa_pct",
            label="GNPA (%)",
            inputs=("gnpa_amt", "aum"),
            calculator=lambda d: _percentage(d.get("gnpa_amt"), d.get("aum")),
            category="asset_quality",
        ),
        RatioDefinition(
            key="nnpa_pct",
            label="NNPA (%)",
            inputs=("nnpa_amt", "aum"),
            calculator=lambda d: _percentage(d.get("nnpa_amt"), d.get("aum")),
            category="asset_quality",
        ),
        RatioDefinition(
            key="leverage_ratio",
            label="Leverage Ratio (x)",
            inputs=("total_assets", "net_worth"),
            calculator=lambda d: safe_divide(d.get("total_assets"), d.get("net_worth")),
            category="leverage",
        ),
        RatioDefinition(
            key="liquidity_ratio",
            label="Liquidity Ratio (x)",
            inputs=("current_assets", "current_liabilities"),
            calculator=lambda d: safe_divide(d.get("current_assets"), d.get("current_liabilities")),
            category="liquidity",
        ),
    )


def safe_divide(numerator: Any, denominator: Any) -> float | None:
    """Divide safely and return None for missing, invalid, or zero denominators."""
    n = _to_number(numerator)
    d = _to_number(denominator)
    if n is None or d in (None, 0):
        return None
    return n / d


def _percentage(numerator: Any, denominator: Any) -> float | None:
    value = safe_divide(numerator, denominator)
    return None if value is None else value * 100


def _round_ratio(value: Any) -> float | None:
    number = _to_number(value)
    return None if number is None else round(number, 2)


def _missing_inputs(data: dict[str, Any], inputs: tuple[str, ...]) -> list[str]:
    return [field for field in inputs if data.get(field) is None]


def _to_number(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, str) and value.strip() in {"", "-", "--", "na", "NA", "N/A", "n/a"}:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    try:
        number = float(str(value).replace(",", "").replace("%", "").strip())
    except (TypeError, ValueError):
        return None
    if np.isnan(number) or np.isinf(number):
        return None
    return number


def ratio_summary(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Return ratio rows with simple credit signals for dashboard display."""
    ratio_data = data.get("calculated_ratios", data)
    fields = [
        ("ROA (%)", "roa", lambda x: "Good" if x is not None and x > 1.5 else ("Watch" if x is not None and x > 0.5 else "Weak")),
        ("ROE (%)", "roe", lambda x: "Good" if x is not None and x > 12 else ("Watch" if x is not None and x > 6 else "Weak")),
        ("Debt / Equity (x)", "debt_equity", lambda x: "Good" if x is not None and x < 5 else ("Watch" if x is not None and x < 7 else "Weak")),
        ("Interest Coverage (x)", "interest_coverage", lambda x: "Good" if x is not None and x > 2 else ("Watch" if x is not None and x > 1.2 else "Weak")),
        ("Current Ratio (x)", "liquidity_ratio", lambda x: "Good" if x is not None and x > 1.2 else ("Watch" if x is not None and x > 1 else "Weak")),
        ("GNPA (%)", "gnpa_pct", lambda x: "Good" if x is not None and x < 3 else ("Watch" if x is not None and x < 6 else "Weak")),
        ("NNPA (%)", "nnpa_pct", lambda x: "Good" if x is not None and x < 1 else ("Watch" if x is not None and x < 3 else "Weak")),
        ("Leverage (x)", "leverage_ratio", lambda x: "Good" if x is not None and x < 6 else ("Watch" if x is not None and x < 8 else "Weak")),
    ]
    rows = []
    for label, key, interpret in fields:
        value = _round_ratio(ratio_data.get(key))
        rows.append({"Metric": label, "Value": value, "Signal": interpret(value)})
    return rows
