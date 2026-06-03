"""
ratios.py
---------
NBFC Ratio Intelligence Engine.

This module calculates explainable NBFC profitability, asset quality,
liquidity, and leverage ratios from standardized mapped financial data.
It deliberately avoids dashboard, scoring, and ML responsibilities.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Callable


Number = int | float
RatioCalculator = Callable[[dict[str, float | None]], float | None]


@dataclass(frozen=True)
class RatioDefinition:
    """Declarative ratio configuration for scalable future additions."""

    field: str
    category: str
    required_inputs: tuple[str, ...]
    calculator: RatioCalculator


RATIO_FIELDS: tuple[str, ...] = (
    "yield_pct",
    "cost_of_funds_pct",
    "nim_pct",
    "credit_cost_pct",
    "roa_pct",
    "roe_pct",
    "avg_cost_of_borrowing_pct",
    "gnpa_pct",
    "nnpa_pct",
    "car_pct",
)


def calculate_ratios(mapped_data: dict[str, Any]) -> dict[str, Any]:
    """
    Calculate NBFC ratios from standardized mapped financial data.

    Existing ratio values in mapped_data are retained and never overwritten.
    Missing or impossible calculations return None instead of raising errors.
    """
    if not isinstance(mapped_data, dict):
        raise TypeError("calculate_ratios expects mapped_data to be a dictionary.")

    normalized_data = {
        field: _to_number(value)
        for field, value in mapped_data.items()
    }

    calculated_ratios: dict[str, float | None] = {}
    missing_inputs: list[str] = []

    for definition in _ratio_definitions():
        existing_value = normalized_data.get(definition.field)
        if existing_value is not None:
            calculated_ratios[definition.field] = round_ratio(existing_value)
            continue

        value = definition.calculator(normalized_data)
        calculated_ratios[definition.field] = round_ratio(value)

        if value is None:
            missing_inputs.extend(
                _missing_inputs(normalized_data, definition.required_inputs)
            )

    missing_inputs = sorted(set(missing_inputs))
    ratio_metadata = {
        "calculated_fields": sum(
            value is not None for value in calculated_ratios.values()
        ),
        "missing_inputs": missing_inputs,
        "calculation_confidence": calculate_confidence(
            calculated_ratios=calculated_ratios,
            missing_inputs=missing_inputs,
            total_ratio_fields=len(RATIO_FIELDS),
        ),
    }

    # Preserve the existing app/scoring contract while exposing the new
    # enterprise ratio payload requested by the intelligence layer.
    enriched_data = dict(mapped_data)
    enriched_data.update(calculated_ratios)
    enriched_data.update(_legacy_ratio_aliases(enriched_data, normalized_data))
    enriched_data["calculated_ratios"] = calculated_ratios
    enriched_data["ratio_metadata"] = ratio_metadata
    enriched_data["missing_inputs"] = missing_inputs
    enriched_data["calculation_confidence"] = ratio_metadata["calculation_confidence"]
    enriched_data["calculated_fields"] = ratio_metadata["calculated_fields"]

    return enriched_data


def safe_divide(numerator: Any, denominator: Any) -> float | None:
    """Return numerator / denominator, or None for invalid or zero inputs."""
    clean_numerator = _to_number(numerator)
    clean_denominator = _to_number(denominator)

    if clean_numerator is None or clean_denominator is None:
        return None
    if clean_denominator == 0:
        return None

    return clean_numerator / clean_denominator


def round_ratio(value: Any) -> float | None:
    """Round a ratio to two decimal places after numeric cleanup."""
    number = _to_number(value)
    if number is None:
        return None
    return round(number, 2)


def calculate_confidence(
    calculated_ratios: dict[str, float | None],
    missing_inputs: list[str],
    total_ratio_fields: int | None = None,
) -> float:
    """
    Estimate calculation confidence from ratio coverage and data completeness.

    The score remains deterministic and transparent: available ratio coverage is
    the base, with a small penalty for unresolved missing inputs. A fully
    covered rules-based calculation is capped below 1.0 to avoid implying model-
    grade certainty.
    """
    total_fields = total_ratio_fields or len(calculated_ratios)
    if total_fields <= 0:
        return 0.0

    available_fields = sum(value is not None for value in calculated_ratios.values())
    coverage_score = available_fields / total_fields
    missing_penalty = min(len(set(missing_inputs)) * 0.02, 0.2)

    return round(max(0.0, min(0.95, coverage_score - missing_penalty)), 2)


def ratio_summary(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Return dashboard-friendly ratio rows with simple credit signals."""
    ratio_data = data.get("calculated_ratios", data)
    fields = [
        (
            "Yield (%)",
            "yield_pct",
            lambda x: "Good" if x is not None and x >= 16 else ("Watch" if x is not None and x >= 12 else "Weak"),
        ),
        (
            "NIM (%)",
            "nim_pct",
            lambda x: "Good" if x is not None and x >= 6 else ("Watch" if x is not None and x >= 3 else "Weak"),
        ),
        (
            "ROA (%)",
            "roa_pct",
            lambda x: "Good" if x is not None and x > 1.5 else ("Watch" if x is not None and x > 0.5 else "Weak"),
        ),
        (
            "ROE (%)",
            "roe_pct",
            lambda x: "Good" if x is not None and x > 12 else ("Watch" if x is not None and x > 6 else "Weak"),
        ),
        (
            "Cost of Funds (%)",
            "cost_of_funds_pct",
            lambda x: "Good" if x is not None and x < 8 else ("Watch" if x is not None and x < 11 else "Weak"),
        ),
        (
            "Credit Cost (%)",
            "credit_cost_pct",
            lambda x: "Good" if x is not None and x < 1.5 else ("Watch" if x is not None and x < 3 else "Weak"),
        ),
        (
            "GNPA (%)",
            "gnpa_pct",
            lambda x: "Good" if x is not None and x < 3 else ("Watch" if x is not None and x < 6 else "Weak"),
        ),
        (
            "NNPA (%)",
            "nnpa_pct",
            lambda x: "Good" if x is not None and x < 1 else ("Watch" if x is not None and x < 3 else "Weak"),
        ),
        (
            "CAR (%)",
            "car_pct",
            lambda x: "Good" if x is not None and x >= 18 else ("Watch" if x is not None and x >= 15 else "Weak"),
        ),
    ]

    rows: list[dict[str, Any]] = []
    for label, key, interpret in fields:
        value = round_ratio(ratio_data.get(key))
        rows.append({"Metric": label, "Value": value, "Signal": interpret(value)})
    return rows


def _ratio_definitions() -> tuple[RatioDefinition, ...]:
    return (
        RatioDefinition(
            field="yield_pct",
            category="profitability",
            required_inputs=("operating_revenue", "aum_on_book"),
            calculator=lambda d: _percentage(
                d.get("operating_revenue"),
                d.get("aum_on_book"),
            ),
        ),
        RatioDefinition(
            field="cost_of_funds_pct",
            category="liquidity",
            required_inputs=("finance_cost", "aum_on_book"),
            calculator=lambda d: _percentage(
                d.get("finance_cost"),
                d.get("aum_on_book"),
            ),
        ),
        RatioDefinition(
            field="nim_pct",
            category="profitability",
            required_inputs=("operating_revenue", "finance_cost", "aum_on_book"),
            calculator=_calculate_nim_pct,
        ),
        RatioDefinition(
            field="credit_cost_pct",
            category="asset_quality",
            required_inputs=("aum_total",),
            calculator=_calculate_credit_cost_pct,
        ),
        RatioDefinition(
            field="roa_pct",
            category="profitability",
            required_inputs=("pat", "aum_total"),
            calculator=lambda d: _percentage(d.get("pat"), d.get("aum_total")),
        ),
        RatioDefinition(
            field="roe_pct",
            category="profitability",
            required_inputs=("pat", "net_worth"),
            calculator=lambda d: _percentage(d.get("pat"), d.get("net_worth")),
        ),
        RatioDefinition(
            field="avg_cost_of_borrowing_pct",
            category="leverage",
            required_inputs=("finance_cost", "borrowings"),
            calculator=lambda d: _percentage(
                d.get("finance_cost"),
                d.get("borrowings"),
            ),
        ),
        RatioDefinition(
            field="gnpa_pct",
            category="asset_quality",
            required_inputs=("stage_3_assets", "aum_on_book"),
            calculator=lambda d: _percentage(
                d.get("stage_3_assets"),
                d.get("aum_on_book"),
            ),
        ),
        RatioDefinition(
            field="nnpa_pct",
            category="asset_quality",
            required_inputs=("stage_3_assets", "provisions", "aum_on_book"),
            calculator=_calculate_nnpa_pct,
        ),
        RatioDefinition(
            field="car_pct",
            category="leverage",
            required_inputs=("capital", "risk_weighted_assets"),
            calculator=_calculate_car_pct,
        ),
    )


def _calculate_nim_pct(data: dict[str, float | None]) -> float | None:
    yield_pct = data.get("yield_pct")
    if yield_pct is None:
        yield_pct = _percentage(data.get("operating_revenue"), data.get("aum_on_book"))

    cost_of_funds_pct = data.get("cost_of_funds_pct")
    if cost_of_funds_pct is None:
        cost_of_funds_pct = _percentage(data.get("finance_cost"), data.get("aum_on_book"))

    if yield_pct is None or cost_of_funds_pct is None:
        return None
    return yield_pct - cost_of_funds_pct


def _calculate_credit_cost_pct(data: dict[str, float | None]) -> float | None:
    provisions = data.get("provisions") or 0.0
    write_offs = _first_available(data, ("write_offs", "write_off_net")) or 0.0

    if provisions == 0 and write_offs == 0:
        return None

    return _percentage(provisions + write_offs, data.get("aum_total"))


def _calculate_nnpa_pct(data: dict[str, float | None]) -> float | None:
    stage_3_assets = data.get("stage_3_assets")
    provisions = data.get("provisions")
    if stage_3_assets is None or provisions is None:
        return None

    return _percentage(stage_3_assets - provisions, data.get("aum_on_book"))


def _calculate_car_pct(data: dict[str, float | None]) -> float | None:
    existing_car = _first_available(data, ("car_pct", "crar"))
    if existing_car is not None:
        return existing_car

    capital = _first_available(
        data,
        (
            "capital",
            "regulatory_capital",
            "total_capital",
            "tier_1_capital",
        ),
    )
    risk_weighted_assets = _first_available(
        data,
        (
            "risk_weighted_assets",
            "rwa",
            "risk_weighted_asset",
        ),
    )

    return _percentage(capital, risk_weighted_assets)


def _legacy_ratio_aliases(
    enriched_data: dict[str, Any],
    normalized_data: dict[str, float | None],
) -> dict[str, float | None]:
    """Keep older dashboard/scoring field names available without overwrites."""
    aliases: dict[str, float | None] = {}

    if enriched_data.get("roa") is None:
        aliases["roa"] = round_ratio(enriched_data.get("roa_pct"))
    if enriched_data.get("roe") is None:
        aliases["roe"] = round_ratio(enriched_data.get("roe_pct"))
    if enriched_data.get("car") is None:
        aliases["car"] = round_ratio(enriched_data.get("car_pct"))
    if enriched_data.get("debt_equity") is None:
        aliases["debt_equity"] = round_ratio(
            safe_divide(normalized_data.get("borrowings"), normalized_data.get("net_worth"))
        )
    if enriched_data.get("leverage_ratio") is None:
        aliases["leverage_ratio"] = round_ratio(
            safe_divide(normalized_data.get("aum_total"), normalized_data.get("net_worth"))
        )
    if enriched_data.get("liquidity_ratio") is None:
        liquid_assets = _sum_available(
            normalized_data,
            ("cash_and_bank", "investments", "current_assets"),
        )
        aliases["liquidity_ratio"] = round_ratio(
            safe_divide(liquid_assets, normalized_data.get("current_liabilities"))
        )

    return aliases


def _percentage(numerator: Any, denominator: Any) -> float | None:
    value = safe_divide(numerator, denominator)
    if value is None:
        return None
    return value * 100


def _missing_inputs(
    data: dict[str, float | None],
    required_inputs: tuple[str, ...],
) -> list[str]:
    return [
        field
        for field in required_inputs
        if data.get(field) is None or data.get(field) == 0
    ]


def _first_available(
    data: dict[str, float | None],
    fields: tuple[str, ...],
) -> float | None:
    for field in fields:
        value = data.get(field)
        if value is not None:
            return value
    return None


def _sum_available(
    data: dict[str, float | None],
    fields: tuple[str, ...],
) -> float | None:
    values = [data.get(field) for field in fields if data.get(field) is not None]
    if not values:
        return None
    return sum(values)


def _to_number(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, (int, float)):
        return float(value) if math.isfinite(float(value)) else None
    if isinstance(value, str):
        cleaned_value = value.strip()
        if cleaned_value.lower() in {"", "-", "--", "na", "n/a", "none", "null"}:
            return None
        cleaned_value = cleaned_value.replace(",", "").replace("%", "")
        try:
            number = float(cleaned_value)
        except ValueError:
            return None
        return number if math.isfinite(number) else None

    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


if __name__ == "__main__":
    sample_mapped_input = {
        "aum_total": 120000,
        "aum_on_book": 100000,
        "finance_cost": 8000,
        "operating_revenue": 18000,
        "pat": 3200,
        "net_worth": 25000,
        "borrowings": 70000,
        "stage_3_assets": 4500,
        "provisions": 1200,
        "car_pct": 22.0,
    }

    ratio_result = calculate_ratios(sample_mapped_input)
    print(ratio_result["calculated_ratios"])
    print(ratio_result["ratio_metadata"])
