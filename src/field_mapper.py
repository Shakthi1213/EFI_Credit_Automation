"""
field_mapper.py
---------------
Maps raw financial line-item names (from PDFs / Excel) to standardized
internal field names used across the entire project.

Supports:
  - Exact match (after normalisation)
  - Fuzzy match via rapidfuzz (handles typos, slight wording differences)
  - Case-insensitive, strip punctuation/spaces before matching
"""

import re
from rapidfuzz import process, fuzz

# ─────────────────────────────────────────────────────────────────────────────
# MASTER MAPPING DICTIONARY
# Keys   = standardised internal field name
# Values = list of known aliases (all lowercase, no punctuation)
# ─────────────────────────────────────────────────────────────────────────────

FIELD_ALIASES: dict[str, list[str]] = {
    # ── Income Statement ──────────────────────────────────────────────────────
    "revenue": [
        "revenue", "total income", "operating income", "net revenue",
        "total revenue", "gross income", "income from operations",
        "net interest income and other income", "total operating income",
    ],
    "pat": [
        "pat", "profit after tax", "net profit", "net income",
        "profit attributable to owners", "profit for the year",
        "profit after taxation", "net earnings", "bottom line profit",
        "profit attributable to equity holders",
    ],
    "pbt": [
        "pbt", "profit before tax", "profit before taxation",
        "earnings before tax", "ebt", "pre tax profit",
    ],
    "ebit": [
        "ebit", "operating profit", "earnings before interest and tax",
        "earnings before interest tax", "profit before interest and tax",
        "pbit", "operating earnings",
    ],
    "ebitda": [
        "ebitda", "operating ebitda",
        "earnings before interest tax depreciation and amortisation",
        "earnings before interest tax depreciation amortisation",
        "ebitda margin", "ebidta",   # common typo
    ],
    "interest_expense": [
        "interest expense", "finance cost", "finance costs",
        "borrowing cost", "interest cost", "interest charges",
        "cost of borrowings", "interest on borrowings",
        "interest paid", "interest and finance charges",
    ],
    "depreciation": [
        "depreciation", "depreciation and amortisation",
        "depreciation amortisation", "d&a", "da",
    ],

    # ── Balance Sheet – Assets ────────────────────────────────────────────────
    "total_assets": [
        "total assets", "asset base", "total balance sheet size",
        "balance sheet total", "total asset base",
    ],
    "current_assets": [
        "current assets", "total current assets", "short term assets",
    ],
    "cash_and_bank": [
        "cash and bank", "cash and bank balance", "cash and cash equivalents",
        "cash equivalents", "cash and balances with banks",
        "balances with banks and cash",
    ],

    # ── Balance Sheet – Liabilities & Equity ─────────────────────────────────
    "net_worth": [
        "net worth", "shareholders funds", "shareholders equity",
        "equity attributable to owners", "total equity",
        "tangible net worth", "book value equity",
        "equity share capital and reserves",
    ],
    "total_debt": [
        "total debt", "borrowings", "debt", "financial liabilities",
        "loans outstanding", "total borrowings", "total liabilities borrowings",
        "outstanding debt", "aggregate borrowings",
    ],
    "current_liabilities": [
        "current liabilities", "total current liabilities",
        "short term liabilities",
    ],
    "short_term_borrowings": [
        "short term borrowings", "short-term debt", "commercial paper",
        "cp", "working capital borrowings", "current maturities of long term debt",
    ],
    "long_term_borrowings": [
        "long term borrowings", "long-term debt", "non current borrowings",
        "term loans", "ncd", "non convertible debentures",
    ],
    "reserves_and_surplus": [
        "reserves and surplus", "reserves", "retained earnings",
        "accumulated surplus", "free reserves",
    ],
    "provisions": [
        "provisions", "total provisions", "provision for npa",
        "provision for bad debts", "credit loss provisions",
        "expected credit loss provision", "ecl provision",
    ],

    # ── AUM / Loan Book ───────────────────────────────────────────────────────
    "aum": [
        "aum", "assets under management", "loan book",
        "managed assets", "total loan book", "portfolio size",
        "gross loan portfolio", "total portfolio",
    ],

    # ── Capital Adequacy ──────────────────────────────────────────────────────
    "car": [
        "car", "crar", "capital adequacy ratio",
        "capital to risk weighted assets ratio",
        "capital to risk assets ratio", "tier 1 and tier 2 capital ratio",
    ],
    "tier1_capital": [
        "tier 1 capital", "tier i capital", "core capital",
        "cet1", "common equity tier 1",
    ],

    # ── Asset Quality ─────────────────────────────────────────────────────────
    "gnpa_pct": [
        "gnpa %", "gnpa percent", "gnpa percentage", "gross npa %",
        "gross npa ratio", "gross npa percentage", "gross npa pct",
        "gross impaired assets ratio", "gross stage 3 ratio", "gross npl ratio",
        "gross npa as a percent", "gross npa as percent of advances",
    ],
    "nnpa_pct": [
        "nnpa %", "nnpa percent", "nnpa percentage", "net npa %",
        "net npa ratio", "net npa percentage", "net npa pct",
        "net impaired assets ratio", "net stage 3 ratio", "net npl ratio",
        "net npa as a percent", "net npa as percent of advances",
    ],
    "gnpa_amt": [
        "gnpa amount", "gross npa amount", "gross impaired assets",
        "gross stage 3 assets", "gross non performing assets amount",
        "total gross npa",
    ],
    "nnpa_amt": [
        "nnpa amount", "net npa amount", "net impaired assets",
        "net stage 3 assets", "net non performing assets amount",
        "total net npa",
    ],
    "pcr": [
        "pcr", "provision coverage ratio", "provision coverage",
        "loan loss coverage ratio",
    ],
    "collection_efficiency": [
        "collection efficiency", "repayment collection efficiency",
        "ce", "collection efficiency ratio",
    ],
    "write_offs": [
        "write offs", "write-offs", "loans written off",
        "bad debts written off",
    ],

    # ── Liquidity / ALM ───────────────────────────────────────────────────────
    "funding_cost": [
        "funding cost", "cost of funds", "average cost of borrowings",
        "weighted average cost of funds", "wacf",
    ],
    "liquidity_ratio": [
        "liquidity ratio", "current ratio", "liquidity coverage ratio",
        "lcr",
    ],
}

# ─────────────────────────────────────────────────────────────────────────────
# Build a flat lookup  {alias: standard_field}  for O(1) exact matching
# ─────────────────────────────────────────────────────────────────────────────
_EXACT_LOOKUP: dict[str, str] = {}
for _field, _aliases in FIELD_ALIASES.items():
    for _alias in _aliases:
        _EXACT_LOOKUP[_alias] = _field

_ALL_ALIASES = list(_EXACT_LOOKUP.keys())


def _normalise(text: str) -> str:
    """Lowercase, strip punctuation and extra spaces."""
    text = text.lower()
    text = re.sub(r"[^a-z0-9 ]", " ", text)   # remove punctuation
    text = re.sub(r"\s+", " ", text).strip()
    return text


def map_field(raw_name: str, fuzzy_threshold: int = 80) -> str | None:
    """
    Map a raw line-item name to a standard internal field name.

    Parameters
    ----------
    raw_name        : The raw string extracted from a PDF or Excel cell.
    fuzzy_threshold : Minimum RapidFuzz score (0-100) to accept a fuzzy match.

    Returns
    -------
    Standard field name (str) or None if no match found.

    Examples
    --------
    >>> map_field("Profit After Tax")
    'pat'
    >>> map_field("Net NPA %")
    'nnpa_pct'
    >>> map_field("Total Borroings")   # typo
    'total_debt'
    """
    if not raw_name or not isinstance(raw_name, str):
        return None

    normalised = _normalise(raw_name)

    # 1. Exact match
    if normalised in _EXACT_LOOKUP:
        return _EXACT_LOOKUP[normalised]

    # 2. Fuzzy match
    result = process.extractOne(
        normalised, _ALL_ALIASES,
        scorer=fuzz.token_sort_ratio,
        score_cutoff=fuzzy_threshold,
    )
    if result:
        matched_alias, _score, _ = result
        return _EXACT_LOOKUP[matched_alias]

    return None


def map_row_dict(raw_dict: dict) -> dict:
    """
    Given a dict of {raw_label: value}, return {standard_field: value}.
    Unmapped keys are included under their original (normalised) name.
    """
    mapped = {}
    for raw_key, value in raw_dict.items():
        std = map_field(str(raw_key))
        mapped[std if std else _normalise(str(raw_key))] = value
    return mapped


def get_all_standard_fields() -> list[str]:
    """Return the sorted list of all standard field names."""
    return sorted(FIELD_ALIASES.keys())
