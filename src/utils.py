"""
utils.py
--------
Shared utility functions:
  - Numeric value cleaning (handles ₹, Cr, Mn, %, brackets, commas)
  - Unit normalisation (crore → absolute, million → absolute)
  - Safe division
  - DataFrame helpers
"""

import re
import numpy as np
import pandas as pd


# ─────────────────────────────────────────────────────────────────────────────
# Numeric Cleaning
# ─────────────────────────────────────────────────────────────────────────────

def clean_numeric(value, unit: str = "cr") -> float | None:
    """
    Parse a raw financial value string into a clean float (in Crores by default).

    Handles:
      ₹10,004 Cr  →  10004.0
      (500)       →  -500.0   (bracketed = negative)
      5.2%        →  5.2
      1,23,456    →  123456.0
      12.5 Mn     →  1.25  (converted from millions to crores)
      --          →  None

    Parameters
    ----------
    value : Raw cell value (str, int, float)
    unit  : Target unit for the output. 'cr' = crores, 'mn' = millions.
    """
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value) if not np.isnan(float(value)) else None

    s = str(value).strip()

    # Blank / dash / NA markers
    if s in ("", "-", "--", "NA", "N/A", "n/a", "nil", "Nil", "NIL"):
        return None

    # Detect negative bracket notation  e.g. (500)  or  (5,000.20)
    negative = False
    if s.startswith("(") and s.endswith(")"):
        s = s[1:-1]
        negative = True

    # Strip currency symbols and whitespace
    s = re.sub(r"[₹$€£,\s]", "", s)

    # Remove % sign (keep value as-is, caller interprets as percentage)
    s = s.replace("%", "")

    # Detect unit multiplier suffix
    multiplier = 1.0
    if re.search(r"(?i)cr(ore)?s?$", s):
        s = re.sub(r"(?i)cr(ore)?s?$", "", s)
        multiplier = 1.0           # already in crores
    elif re.search(r"(?i)mn$|million$", s):
        s = re.sub(r"(?i)(mn|million)$", "", s)
        multiplier = 0.1           # 1 million = 0.1 crore (1 cr = 10 mn)
    elif re.search(r"(?i)bn$|billion$", s):
        s = re.sub(r"(?i)(bn|billion)$", "", s)
        multiplier = 100.0         # 1 billion = 100 crores
    elif re.search(r"(?i)lakh(s)?$", s):
        s = re.sub(r"(?i)lakh(s)?$", "", s)
        multiplier = 0.01          # 1 lakh = 0.01 crore

    s = s.strip()

    try:
        num = float(s) * multiplier
        return -num if negative else num
    except ValueError:
        return None


def clean_series(series: pd.Series, unit: str = "cr") -> pd.Series:
    """Apply clean_numeric to an entire pandas Series."""
    return series.apply(lambda x: clean_numeric(x, unit))


def safe_divide(numerator, denominator) -> float | None:
    """Divide two values; return None on zero division or None inputs."""
    try:
        n = float(numerator)
        d = float(denominator)
        if d == 0:
            return None
        return n / d
    except (TypeError, ValueError):
        return None


def pct_change(new_val, old_val) -> float | None:
    """Return percentage change from old_val to new_val."""
    try:
        n, o = float(new_val), float(old_val)
        if o == 0:
            return None
        return round(((n - o) / abs(o)) * 100, 2)
    except (TypeError, ValueError):
        return None


# ─────────────────────────────────────────────────────────────────────────────
# DataFrame helpers
# ─────────────────────────────────────────────────────────────────────────────

def ensure_numeric_columns(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    """Force a list of columns to numeric, coercing errors to NaN."""
    for col in cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def fill_missing_columns(df: pd.DataFrame, required_cols: list[str]) -> pd.DataFrame:
    """Add any missing required columns as NaN."""
    for col in required_cols:
        if col not in df.columns:
            df[col] = np.nan
    return df


# ─────────────────────────────────────────────────────────────────────────────
# Standard column list (also used as Excel header reference)
# ─────────────────────────────────────────────────────────────────────────────

IDENTIFICATION_COLS = [
    "company_name", "company_id", "quarter", "year", "report_type",
    "sector", "sub_sector", "external_rating", "rating_outlook",
    "rating_agency", "source_file", "source_page",
]

FINANCIAL_COLS = [
    "revenue", "pat", "pbt", "ebit", "ebitda", "interest_expense",
    "total_assets", "net_worth", "total_debt", "current_assets",
    "current_liabilities", "cash_and_bank", "reserves_and_surplus", "provisions",
]

GROWTH_COLS = [
    "aum", "aum_growth_yoy", "revenue_growth_yoy", "pat_growth_yoy",
]

RATIO_COLS = [
    "roa", "roe", "debt_equity", "interest_coverage", "car",
    "gnpa_pct", "nnpa_pct", "pcr", "collection_efficiency",
    "liquidity_ratio", "leverage_ratio",
]

ASSET_QUALITY_COLS = [
    "gnpa_amt", "nnpa_amt", "write_offs", "restructured_book",
    "sma_0", "sma_1", "sma_2",
]

BORROWING_COLS = [
    "short_term_borrowings", "long_term_borrowings", "total_borrowings",
    "funding_cost", "cp_dependence", "alm_gap_0_30", "alm_gap_31_90",
    "alm_gap_91_180", "top_5_lender_share",
]

GOVERNANCE_COLS = [
    "auditor_change_flag", "management_change_flag", "promoter_pledge_pct",
    "regulatory_issue_flag", "related_party_flag", "news_sentiment",
    "governance_score",
]

LABEL_COLS = [
    "rating_change", "downgrade_flag", "stress_flag",
    "default_flag", "risk_label",
]

ALL_COLS = (
    IDENTIFICATION_COLS + FINANCIAL_COLS + GROWTH_COLS +
    RATIO_COLS + ASSET_QUALITY_COLS + BORROWING_COLS +
    GOVERNANCE_COLS + LABEL_COLS
)
