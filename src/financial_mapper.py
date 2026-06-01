"""
financial_mapper.py
-------------------
Enterprise mapping engine for NBFC financial line items.

The mapper standardizes labels extracted from annual reports, investor decks,
rating notes, OCR output, and Excel files into canonical field names used by
the credit intelligence layer.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd
from rapidfuzz import fuzz, process


FUZZY_THRESHOLD = 86


FINANCIAL_MAPPING: dict[str, list[str]] = {
    "gnpa_amt": [
        "gnpa", "gross npa", "gross npas", "gross npa amount", "gross npa amt",
        "gross non performing asset", "gross non performing assets",
        "gross non-performing assets", "gross impaired assets",
        "gross impaired loans", "gross npl", "gross npls",
        "gross stage 3 assets", "gross stage iii assets",
        "gross stage-iii assets", "gross stage 3 loans",
        "stage 3 gross exposure", "total gross npa", "gross npa cr",
    ],
    "nnpa_amt": [
        "nnpa", "net npa", "net npas", "net npa amount", "net npa amt",
        "net non performing asset", "net non performing assets",
        "net non-performing assets", "net impaired assets",
        "net impaired loans", "net npl", "net npls",
        "net stage 3 assets", "net stage iii assets", "net stage-iii assets",
        "stage 3 net exposure", "total net npa", "net npa cr",
    ],
    "gnpa_pct": [
        "gnpa percent", "gnpa percentage", "gnpa ratio", "gnpa %",
        "gross npa percent", "gross npa percentage", "gross npa ratio",
        "gross npa %", "gross npa as percent of advances",
        "gross npa as percentage of aum", "gross stage 3 ratio",
        "gross stage iii ratio", "gross impaired assets ratio",
    ],
    "nnpa_pct": [
        "nnpa percent", "nnpa percentage", "nnpa ratio", "nnpa %",
        "net npa percent", "net npa percentage", "net npa ratio",
        "net npa %", "net npa as percent of advances",
        "net npa as percentage of aum", "net stage 3 ratio",
        "net stage iii ratio", "net impaired assets ratio",
    ],
    "pcr": [
        "pcr", "provision coverage", "provision coverage ratio",
        "provision coverage ratio pcr", "pcr percent", "pcr %",
        "loan loss coverage ratio", "npa provision coverage",
        "stage 3 provision coverage",
    ],
    "provisions": [
        "provisions", "total provisions", "loan loss provisions",
        "impairment allowance", "impairment allowances", "impairment loss",
        "expected credit loss", "expected credit losses", "ecl",
        "ecl provision", "provisions ecl", "provision for npa",
        "provision for bad debts", "credit loss provision",
        "credit loss provisions",
    ],
    "write_offs": [
        "write off", "write offs", "write-off", "write-offs", "written off",
        "loans written off", "bad debts written off", "technical write off",
        "technical write offs", "writeoffs",
    ],
    "stage_1_assets": [
        "stage 1 assets", "stage i assets", "stage-one assets",
        "gross stage 1 assets", "standard assets", "ind as stage 1 assets",
        "stage 1 loans", "stage i loans", "stage 1 exposure",
    ],
    "stage_2_assets": [
        "stage 2 assets", "stage ii assets", "stage-two assets",
        "gross stage 2 assets", "ind as stage 2 assets", "stage 2 loans",
        "stage ii loans", "stage 2 exposure", "underperforming assets",
    ],
    "stage_3_assets": [
        "stage 3 assets", "stage iii assets", "stage-three assets",
        "gross stage 3 assets", "gross stage iii assets",
        "ind as stage 3 assets", "stage 3 loans", "stage iii loans",
        "credit impaired assets", "impaired assets",
    ],
    "credit_cost": [
        "credit cost", "credit costs", "credit cost ratio",
        "annualised credit cost", "annualized credit cost",
        "loan loss expense", "impairment cost", "provisioning cost",
        "cost of credit", "credit loss expense",
    ],
    "restructured_assets": [
        "restructured assets", "restructured book", "restructured loans",
        "rescheduled loans", "rescheduled assets", "rbi restructuring",
        "covid restructuring", "resolution plan exposure",
    ],
    "slippages": [
        "slippages", "fresh slippages", "gross slippages", "npa additions",
        "new npa additions", "new npa formation", "stage 3 additions",
        "slippage ratio", "slippages during the period",
    ],
    "revenue": [
        "revenue", "total revenue", "total income", "income", "gross income",
        "income from operations", "revenue from operations", "operating revenue",
        "net revenue", "total operating revenue", "revenue total income",
        "revenue / total income", "revenue total income cr", "total income cr",
    ],
    "interest_income": [
        "interest income", "interest earned", "income from lending",
        "income on loans", "interest on loans", "interest on advances",
        "finance income", "financing income", "interest and fee income",
    ],
    "net_interest_income": [
        "net interest income", "nii", "net finance income",
        "net financing income", "net interest earnings",
        "interest income net of finance cost",
    ],
    "pat": [
        "pat", "profit after tax", "profit after taxation", "net profit",
        "net profit after tax", "net income", "net earnings",
        "profit for the year", "profit for the period",
        "profit attributable to owners", "pat net profit", "pat / net profit",
    ],
    "pbt": [
        "pbt", "profit before tax", "profit before taxation",
        "pre tax profit", "pretax profit", "earnings before tax", "ebt",
    ],
    "ebit": [
        "ebit", "earnings before interest and tax",
        "earnings before interest tax", "profit before interest and tax",
        "pbit", "operating earnings", "ebit cr",
    ],
    "ebitda": [
        "ebitda", "ebidta", "operating ebitda",
        "earnings before interest tax depreciation and amortisation",
        "earnings before interest tax depreciation and amortization",
        "profit before depreciation interest and tax",
    ],
    "operating_profit": [
        "operating profit", "profit from operations", "operating earnings",
        "pre provision operating profit", "ppop", "profit before provisions",
        "operating profit before provisions",
    ],
    "operating_income": [
        "operating income", "total operating income", "income from operations",
        "operating revenue", "net operating income",
    ],
    "total_assets": [
        "total assets", "asset base", "total asset base", "balance sheet size",
        "total balance sheet size", "balance sheet total", "assets total",
        "total assets cr", "total assets rs cr",
    ],
    "net_worth": [
        "net worth", "networth", "shareholders funds", "shareholder funds",
        "shareholders equity", "shareholder equity", "total equity", "equity",
        "equity capital and reserves", "owned funds", "tangible net worth",
        "tnw", "book value equity", "net worth equity", "net worth / equity",
    ],
    "total_debt": [
        "total debt", "debt", "borrowings", "total borrowings",
        "total debt borrowings", "debt borrowings", "outstanding debt",
        "aggregate borrowings", "financial liabilities", "loan funds",
        "debt outstanding", "total liabilities borrowings",
        "total debt / borrowings",
    ],
    "borrowings": [
        "borrowing", "borrowings", "total borrowing", "total borrowings",
        "secured borrowings", "unsecured borrowings", "bank borrowings",
        "market borrowings", "debt securities", "ncd",
        "non convertible debentures", "commercial paper", "cp borrowings",
        "term loans",
    ],
    "current_assets": [
        "current assets", "total current assets", "short term assets",
        "current asset", "liquid current assets",
    ],
    "current_liabilities": [
        "current liabilities", "total current liabilities",
        "short term liabilities", "current liability", "short-term liabilities",
    ],
    "cash_and_bank": [
        "cash and bank", "cash bank", "cash & bank", "cash and bank balances",
        "cash and balances with banks", "cash and cash equivalents",
        "cash equivalents", "bank balances", "cash bank cr",
    ],
    "investments": [
        "investments", "current investments", "non current investments",
        "treasury investments", "investment book", "financial investments",
    ],
    "fixed_assets": [
        "fixed assets", "property plant equipment", "ppe",
        "property plant and equipment", "tangible assets", "net fixed assets",
    ],
    "car": [
        "car", "capital adequacy ratio", "capital adequacy", "capital ratio",
        "capital to risk weighted assets ratio",
        "capital to risk assets ratio", "capital adequacy ratio car",
    ],
    "tier_1_capital": [
        "tier 1 capital", "tier i capital", "tier one capital",
        "tier-1 capital", "tier-i capital", "tier 1 ratio", "tier i ratio",
        "common equity tier 1", "cet1", "core capital",
    ],
    "tier_2_capital": [
        "tier 2 capital", "tier ii capital", "tier two capital",
        "tier-2 capital", "tier-ii capital", "tier 2 ratio", "tier ii ratio",
        "supplementary capital",
    ],
    "crar": [
        "crar", "capital to risk weighted assets ratio crar",
        "capital risk adequacy ratio", "capital risk weighted asset ratio",
        "car crar", "car / crar", "capital adequacy crar",
    ],
    "aum": [
        "aum", "assets under management", "asset under management",
        "managed assets", "assets managed", "total aum", "aum loan book",
        "aum / loan book", "gross aum", "closing aum", "average aum",
    ],
    "loan_book": [
        "loan book", "loan portfolio", "gross loan book", "total loan book",
        "gross loan portfolio", "advances", "gross advances",
        "assets under finance", "portfolio outstanding", "portfolio size",
    ],
    "disbursements": [
        "disbursement", "disbursements", "loan disbursements",
        "disbursals", "loan disbursals", "fresh disbursements",
        "originations", "loan originations", "amount disbursed",
    ],
    "interest_expense": [
        "interest expense", "interest expenses", "finance cost",
        "finance costs", "interest finance cost", "interest / finance cost",
        "interest / finance cost cr", "borrowing cost", "borrowing costs",
        "cost of borrowings", "interest cost", "interest paid",
        "interest on borrowings", "finance charges",
        "interest and finance charges",
    ],
    "interest_coverage": [
        "interest coverage", "interest coverage ratio", "icr",
        "ebit interest coverage", "interest cover", "interest coverage x",
        "interest coverage times",
    ],
    "liquidity_ratio": [
        "liquidity ratio", "current ratio", "lcr", "liquidity coverage ratio",
        "liquid assets ratio", "liquid asset ratio", "current assets ratio",
    ],
    "roa": ["roa", "return on assets", "return on asset", "roa percent", "roa %"],
    "roe": ["roe", "return on equity", "return on net worth", "ronw", "roe percent", "roe %"],
    "debt_equity": [
        "debt equity", "debt equity ratio", "debt/equity", "debt to equity",
        "debt-to-equity", "debt equity x", "total debt net worth",
    ],
    "leverage_ratio": [
        "leverage ratio", "leverage", "assets net worth", "assets to net worth",
        "total assets net worth",
    ],
}


@dataclass(frozen=True)
class MappingMatch:
    field: str
    confidence: float
    method: str
    matched_alias: str


def normalize_text(text: Any) -> str:
    """Normalize labels for case, whitespace, punctuation, and OCR noise."""
    if text is None:
        return ""
    normalized = str(text).lower().replace("&", " and ")
    normalized = re.sub(r"\(\s*%\s*\)", " percent ", normalized)
    normalized = normalized.replace("%", " percent ")
    normalized = re.sub(r"\([^)]*\)", " ", normalized)
    normalized = re.sub(r"\[[^]]*\]", " ", normalized)
    normalized = re.sub(r"\b(in|rs|inr|amount|amt)\s*(crores?|crs?|cr)\b", " ", normalized)
    normalized = re.sub(r"\b(crores?|crs?|cr|mn|million|bn|billion|lakh|lakhs)\b", " ", normalized)
    normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
    normalized = re.sub(r"\bn\s*p\s*a\b", "npa", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized


def _is_missing(value: Any) -> bool:
    if value is None:
        return True
    try:
        return bool(pd.isna(value))
    except (TypeError, ValueError):
        return False


def _build_alias_lookup() -> tuple[dict[str, str], list[str]]:
    lookup: dict[str, str] = {}
    for field, aliases in FINANCIAL_MAPPING.items():
        lookup[normalize_text(field)] = field
        for alias in aliases:
            lookup[normalize_text(alias)] = field
    return lookup, sorted(lookup)


_ALIAS_LOOKUP, _NORMALIZED_ALIASES = _build_alias_lookup()


def _match_field(raw_key: Any, fuzzy_threshold: int = FUZZY_THRESHOLD) -> MappingMatch | None:
    normalized_key = normalize_text(raw_key)
    if not normalized_key:
        return None

    if normalized_key in FINANCIAL_MAPPING:
        return MappingMatch(normalized_key, 1.0, "exact_standard_field", normalized_key)

    if normalized_key in _ALIAS_LOOKUP:
        return MappingMatch(_ALIAS_LOOKUP[normalized_key], 1.0, "alias", normalized_key)

    fuzzy_result = process.extractOne(
        normalized_key,
        _NORMALIZED_ALIASES,
        scorer=fuzz.WRatio,
        score_cutoff=fuzzy_threshold,
    )
    if not fuzzy_result:
        return None

    matched_alias, score, _ = fuzzy_result
    return MappingMatch(
        field=_ALIAS_LOOKUP[matched_alias],
        confidence=round(score / 100, 4),
        method="fuzzy",
        matched_alias=matched_alias,
    )


def map_financial_line_items(data_dict: dict[str, Any]) -> dict[str, Any]:
    """
    Map raw financial labels to canonical NBFC fields.

    Returns mapped data, unmatched original fields, aggregate confidence, and
    match-level metadata for explainability and audit trails.
    """
    if not isinstance(data_dict, dict):
        raise TypeError("map_financial_line_items expects a dictionary input.")

    mapped_data: dict[str, Any] = {}
    unmatched_fields: list[str] = []
    mapping_details: dict[str, dict[str, Any]] = {}
    confidence_scores: list[float] = []

    for raw_key, value in data_dict.items():
        if _is_missing(value):
            continue

        match = _match_field(raw_key)
        if not match:
            unmatched_fields.append(str(raw_key))
            continue

        if match.field not in mapped_data or _is_missing(mapped_data.get(match.field)):
            mapped_data[match.field] = value

        mapping_details[str(raw_key)] = {
            "standard_field": match.field,
            "method": match.method,
            "matched_alias": match.matched_alias,
            "confidence": match.confidence,
        }
        confidence_scores.append(match.confidence)

    mapping_confidence = round(float(np.mean(confidence_scores)), 2) if confidence_scores else 0.0

    return {
        "mapped_data": mapped_data,
        "unmatched_fields": unmatched_fields,
        "mapping_confidence": mapping_confidence,
        "mapping_details": mapping_details,
    }


def get_standard_financial_fields() -> list[str]:
    """Return canonical fields currently supported by the mapper."""
    return sorted(FINANCIAL_MAPPING)
