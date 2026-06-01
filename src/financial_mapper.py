"""
financial_mapper.py
-------------------
Enterprise Financial Mapping Engine for NBFC credit intelligence.

This module standardizes financial line-item labels extracted from annual
reports, quarterly updates, investor presentations, rating reports, PDFs, and
OCR output into a reusable canonical schema. It does not calculate ratios or
touch dashboard/scoring logic.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from rapidfuzz import fuzz, process


FUZZY_THRESHOLD = 86
LOW_CONFIDENCE_THRESHOLD = 0.9


FINANCIAL_MAPPING: dict[str, list[str]] = {
    # AUM and growth
    "aum_total": [
        "AUM", "AUM Total", "AUM (Total)", "Total AUM", "Closing AUM",
        "Average AUM", "Gross AUM", "Consolidated AUM", "Assets Under Management",
        "Asset Under Management", "Managed Assets", "Assets Managed",
        "Loan Book", "Gross Loan Book", "Total Loan Book", "Loan Assets",
        "Loan Portfolio", "Gross Loan Portfolio", "Portfolio Outstanding",
        "Portfolio Size", "Assets Under Finance", "AUM / Loan Book",
        "AUM and Loan Book", "Total Managed Portfolio",
    ],
    "aum_on_book": [
        "On Book AUM", "On-book AUM", "On Balance Sheet AUM",
        "Own Book AUM", "Own Loan Book", "On Book Portfolio",
        "On Balance Sheet Portfolio", "Owned Portfolio", "Book AUM",
        "On Book Assets Under Management", "On-book Loan Assets",
    ],
    "aum_off_book": [
        "Off Book AUM", "Off-book AUM", "Off Balance Sheet AUM",
        "Managed Off Book Portfolio", "Assigned Portfolio", "Securitised Portfolio",
        "Securitized Portfolio", "Co Lending AUM", "Co-lending AUM",
        "DA Portfolio", "Direct Assignment Portfolio", "BC Portfolio",
        "Business Correspondent Portfolio", "Off Book Loan Book",
    ],
    "disbursements": [
        "Disbursement", "Disbursements", "Loan Disbursement",
        "Loan Disbursements", "Disbursals", "Loan Disbursals",
        "Fresh Disbursements", "Originations", "Loan Originations",
        "Amount Disbursed", "Total Disbursed", "Quarterly Disbursements",
        "Annual Disbursements", "New Loans Disbursed",
    ],

    # Balance sheet
    "net_worth": [
        "Net Worth", "Networth", "Tangible Net Worth", "TNW",
        "Shareholders Funds", "Shareholder Funds", "Shareholders' Funds",
        "Shareholders Equity", "Shareholder Equity", "Total Equity",
        "Equity", "Owned Funds", "Book Value Equity",
        "Equity Share Capital and Reserves", "Equity Capital and Reserves",
        "Net Worth / Equity", "Net Worth Equity", "Capital and Reserves",
    ],
    "capital_infusion": [
        "Capital Infusion", "Capital Infused", "Equity Infusion",
        "Equity Capital Infusion", "Fresh Capital Infusion",
        "Fresh Equity Infusion", "Capital Raise", "Capital Raised",
        "Equity Raise", "Primary Capital Raise", "Promoter Infusion",
        "Share Capital Infusion", "Funds Infused",
    ],
    "cash_and_bank": [
        "Cash and Bank", "Cash & Bank", "Cash Bank", "Cash and Bank Balances",
        "Cash and Balances with Banks", "Balances with Banks",
        "Cash and Cash Equivalents", "Cash Equivalents", "Bank Balances",
        "Cash Balance", "Cash at Bank", "Liquid Cash", "Cash / Bank",
    ],
    "borrowings": [
        "Borrowings", "Borrowing", "Total Borrowings", "Debt",
        "Total Debt", "Total Debt / Borrowings", "Debt Borrowings",
        "Outstanding Debt", "Aggregate Borrowings", "Financial Liabilities",
        "Loan Funds", "Debt Outstanding", "Secured Borrowings",
        "Unsecured Borrowings", "Bank Borrowings", "Market Borrowings",
        "Debt Securities", "NCD", "NCDs", "Non Convertible Debentures",
        "Non-Convertible Debentures", "Commercial Paper", "CP Borrowings",
        "Term Loans", "External Borrowings", "Refinance Borrowings",
    ],
    "total_assets": [
        "Total Assets", "Assets Total", "Asset Base", "Total Asset Base",
        "Balance Sheet Size", "Total Balance Sheet Size", "Balance Sheet Total",
        "Total Balance Sheet", "Total Assets Owned", "Gross Assets",
    ],
    "current_assets": [
        "Current Assets", "Total Current Assets", "Short Term Assets",
        "Short-term Assets", "Current Asset", "Liquid Current Assets",
    ],
    "current_liabilities": [
        "Current Liabilities", "Total Current Liabilities",
        "Short Term Liabilities", "Short-term Liabilities",
        "Current Liability", "Near Term Liabilities",
    ],
    "investments": [
        "Investments", "Current Investments", "Non Current Investments",
        "Non-current Investments", "Treasury Investments", "Investment Book",
        "Financial Investments", "Investment Portfolio", "Liquid Investments",
    ],
    "fixed_assets": [
        "Fixed Assets", "Net Fixed Assets", "Property Plant Equipment",
        "Property Plant and Equipment", "PPE", "Tangible Assets",
        "Owned Fixed Assets", "Capital Assets",
    ],

    # Income statement
    "operating_revenue": [
        "Operating Revenue", "Revenue from Operations", "Total Operating Revenue",
        "Operating Income", "Total Operating Income", "Revenue", "Total Revenue",
        "Total Income", "Income from Operations", "Gross Income",
        "Net Revenue", "Revenue / Total Income", "Business Income",
        "Income from Financing Activities", "Income from Lending Operations",
    ],
    "derecognition_gain": [
        "Derecognition Gain", "Gain on Derecognition", "Gain on Assignment",
        "Assignment Income", "Securitisation Income", "Securitization Income",
        "Gain on Securitisation", "Gain on Securitization",
        "Direct Assignment Gain", "DA Gain", "Gain on Sale of Loans",
        "Gain on Loan Assignment", "Income from Assigned Portfolio",
    ],
    "finance_cost": [
        "Finance Cost", "Finance Costs", "Interest Expense",
        "Interest Expenses", "Interest / Finance Cost", "Interest Finance Cost",
        "Borrowing Cost", "Borrowing Costs", "Cost of Borrowings",
        "Interest Cost", "Interest Paid", "Interest on Borrowings",
        "Finance Charges", "Interest and Finance Charges", "Funding Cost",
    ],
    "operating_expenses": [
        "Operating Expenses", "Opex", "Operating Cost", "Operating Costs",
        "Employee Expenses", "Administrative Expenses", "Other Operating Expenses",
        "Branch Operating Expenses", "Business Operating Expenses",
        "Total Expenses excluding Finance Cost", "Non Interest Expenses",
    ],
    "ppop": [
        "PPOP", "Pre Provision Operating Profit",
        "Pre-Provision Operating Profit", "Profit Before Provisions",
        "Operating Profit Before Provisions", "Pre Provision Profit",
        "Pre-provision Profit", "Operating Profit before Credit Cost",
    ],
    "provisions": [
        "Provisions", "Total Provisions", "Loan Loss Provisions",
        "Provision Expense", "Provisioning Expense", "Impairment Allowance",
        "Impairment Allowances", "Impairment Loss", "Expected Credit Loss",
        "Expected Credit Losses", "ECL", "ECL Provision", "Provisions / ECL",
        "Provision for NPA", "Provision for Bad Debts", "Credit Loss Provision",
        "Credit Loss Provisions", "Provision and Write Offs",
    ],
    "write_off_net": [
        "Net Write Off", "Net Write Offs", "Net Write-off", "Net Write-offs",
        "Write Off Net", "Write-offs Net of Recoveries",
        "Write Offs Net of Recoveries", "Net Credit Write Offs",
        "Net Loan Write Offs", "Bad Debts Written Off Net",
    ],
    "pbt": [
        "PBT", "Profit Before Tax", "Profit Before Taxation",
        "Pre Tax Profit", "Pretax Profit", "Earnings Before Tax", "EBT",
        "Profit Before Taxes", "Profit Before Income Tax",
    ],
    "pat": [
        "PAT", "Profit After Tax", "Profit After Taxation",
        "Net Profit", "Net Profit After Tax", "PAT / Net Profit",
        "Net Income", "Net Earnings", "Profit for the Period",
        "Profit for the Year", "Profit Attributable to Owners",
        "Profit Attributable to Equity Holders", "Bottom Line Profit",
    ],
    "interest_income": [
        "Interest Income", "Interest Earned", "Income from Lending",
        "Income on Loans", "Interest on Loans", "Interest on Advances",
        "Finance Income", "Financing Income", "Interest and Fee Income",
        "Interest on Loan Assets", "Interest Income on Financing Assets",
    ],
    "net_interest_income": [
        "Net Interest Income", "NII", "Net Finance Income",
        "Net Financing Income", "Net Interest Earnings",
        "Interest Income Net of Finance Cost", "Net Interest Revenue",
        "Net Interest Spread Income",
    ],
    "ebit": [
        "EBIT", "Earnings Before Interest and Tax",
        "Earnings Before Interest Tax", "Profit Before Interest and Tax",
        "PBIT", "Operating Earnings", "Operating Profit after Depreciation",
    ],
    "ebitda": [
        "EBITDA", "EBIDTA", "Operating EBITDA",
        "Earnings Before Interest Tax Depreciation and Amortisation",
        "Earnings Before Interest Tax Depreciation and Amortization",
        "Profit Before Depreciation Interest and Tax",
    ],
    "operating_profit": [
        "Operating Profit", "Profit from Operations", "Operating Earnings",
        "Business Operating Profit", "Core Operating Profit",
        "Operating Profit after Expenses", "Operating Result",
    ],

    # Asset quality
    "gnpa_amt": [
        "GNPA", "Gross NPA", "Gross NPAs", "Gross NPA Amount",
        "Gross NPA Amt", "Gross Non Performing Asset",
        "Gross Non Performing Assets", "Gross Non-Performing Assets",
        "Gross Non-performing Loans", "Gross Impaired Assets",
        "Gross Impaired Loans", "Gross NPL", "Gross NPLs",
        "Gross Stage 3 Assets", "Gross Stage III Assets",
        "Gross Stage-III Assets", "Gross Stage-3 Assets",
        "Gross Stage 3 Loans", "Stage 3 Gross Exposure",
        "Total Gross NPA", "Gross Credit Impaired Assets",
        "Gross Non Performing Advances",
    ],
    "nnpa_amt": [
        "NNPA", "Net NPA", "Net NPAs", "Net NPA Amount", "Net NPA Amt",
        "Net Non Performing Asset", "Net Non Performing Assets",
        "Net Non-Performing Assets", "Net Impaired Assets",
        "Net Impaired Loans", "Net NPL", "Net NPLs", "Net Stage 3 Assets",
        "Net Stage III Assets", "Net Stage-III Assets", "Net Stage-3 Assets",
        "Stage 3 Net Exposure", "Total Net NPA", "Net Credit Impaired Assets",
    ],
    "pcr": [
        "PCR", "Provision Coverage", "Provision Coverage Ratio",
        "Provision Coverage Ratio PCR", "PCR %", "PCR Percent",
        "Loan Loss Coverage Ratio", "NPA Provision Coverage",
        "Stage 3 Provision Coverage", "Coverage Ratio",
    ],
    "credit_cost_pct": [
        "Credit Cost", "Credit Cost %", "Credit Cost Percent",
        "Credit Cost Ratio", "Annualised Credit Cost",
        "Annualized Credit Cost", "Loan Loss Expense Ratio",
        "Impairment Cost Ratio", "Provisioning Cost Ratio",
        "Cost of Credit", "Credit Loss Expense Ratio",
    ],
    "stage_1_assets": [
        "Stage 1 Assets", "Stage I Assets", "Stage-I Assets",
        "Stage One Assets", "Gross Stage 1 Assets", "Standard Assets",
        "IND AS Stage 1 Assets", "Ind-AS Stage 1 Assets",
        "Stage 1 Loans", "Stage I Loans", "Stage 1 Exposure",
    ],
    "stage_2_assets": [
        "Stage 2 Assets", "Stage II Assets", "Stage-II Assets",
        "Stage Two Assets", "Gross Stage 2 Assets",
        "IND AS Stage 2 Assets", "Ind-AS Stage 2 Assets",
        "Stage 2 Loans", "Stage II Loans", "Stage 2 Exposure",
        "Underperforming Assets", "SICR Assets",
    ],
    "stage_3_assets": [
        "Stage 3 Assets", "Stage III Assets", "Stage-III Assets",
        "Stage-3 Assets", "Stage Three Assets", "IND AS Stage 3 Assets",
        "Ind-AS Stage 3 Assets", "Stage 3 Loans", "Stage III Loans",
        "Credit Impaired Assets", "Impaired Assets",
    ],
    "write_offs": [
        "Write Off", "Write Offs", "Write-off", "Write-offs",
        "Written Off", "Loans Written Off", "Bad Debts Written Off",
        "Technical Write Off", "Technical Write Offs", "Writeoffs",
        "Write Off During the Year", "Gross Write Offs",
    ],
    "slippages": [
        "Slippages", "Fresh Slippages", "Gross Slippages", "NPA Additions",
        "New NPA Additions", "New NPA Formation", "Stage 3 Additions",
        "Slippage Ratio", "Slippages During the Period",
        "Fresh Stage 3 Additions",
    ],
    "restructured_assets": [
        "Restructured Assets", "Restructured Book", "Restructured Loans",
        "Restructuring Book", "Rescheduled Loans", "Rescheduled Assets",
        "RBI Restructuring", "Covid Restructuring",
        "Resolution Plan Exposure", "One Time Restructuring",
        "OTR Portfolio", "Stress Resolution Portfolio",
    ],

    # Profitability ratios
    "yield_pct": [
        "Yield", "Yield %", "Yield Percent", "Portfolio Yield",
        "Average Yield", "Yield on Advances", "Yield on Loan Book",
        "Yield on AUM", "Gross Yield", "Loan Yield", "Asset Yield",
    ],
    "nim_pct": [
        "NIM", "NIM %", "Net Interest Margin", "Net Interest Margin %",
        "Net Interest Margin Percent", "Net Interest Spread",
        "Interest Margin", "Spread", "Net Spread",
    ],
    "roa_pct": [
        "ROA", "ROA %", "Return on Assets", "Return on Asset",
        "Return on Average Assets", "RoAA", "ROAA", "ROA Percent",
    ],
    "roe_pct": [
        "ROE", "ROE %", "Return on Equity", "Return on Net Worth",
        "Return on Average Equity", "RoAE", "ROAE", "RONW", "ROE Percent",
    ],

    # Capital adequacy
    "car_pct": [
        "CAR", "CAR %", "Capital Adequacy Ratio", "Capital Adequacy",
        "Capital Ratio", "Regulatory Capital Ratio",
        "Capital to Risk Weighted Assets Ratio",
        "Capital to Risk-Weighted Assets Ratio",
        "Capital to Risk Assets Ratio", "Total Capital Adequacy Ratio",
    ],
    "tier_1_capital": [
        "Tier 1 Capital", "Tier I Capital", "Tier One Capital",
        "Tier-1 Capital", "Tier-I Capital", "Tier 1 Ratio", "Tier I Ratio",
        "Common Equity Tier 1", "CET1", "Core Capital",
        "Tier 1 Capital Adequacy",
    ],
    "tier_2_capital": [
        "Tier 2 Capital", "Tier II Capital", "Tier Two Capital",
        "Tier-2 Capital", "Tier-II Capital", "Tier 2 Ratio", "Tier II Ratio",
        "Supplementary Capital", "Tier 2 Capital Adequacy",
    ],
    "crar": [
        "CRAR", "CRAR %", "Capital Risk Adequacy Ratio",
        "Capital to Risk Weighted Assets Ratio CRAR",
        "Capital Risk Weighted Asset Ratio", "CAR / CRAR",
        "CAR CRAR", "Capital Adequacy CRAR",
    ],

    # Leverage and liquidity
    "debt_equity": [
        "Debt Equity", "Debt Equity Ratio", "Debt/Equity",
        "Debt to Equity", "Debt-to-Equity", "D/E", "D E Ratio",
        "Total Debt Net Worth", "Borrowings to Net Worth",
        "Debt to Net Worth", "Leverage Debt Equity",
    ],
    "interest_coverage": [
        "Interest Coverage", "Interest Coverage Ratio", "ICR",
        "EBIT Interest Coverage", "Interest Cover",
        "Interest Coverage X", "Interest Coverage Times",
        "EBIT / Interest Expense", "Earnings Interest Cover",
    ],
    "cost_of_funds_pct": [
        "Cost of Funds", "Cost of Funds %", "COF", "COF %",
        "Funding Cost", "Funding Cost %", "Average Cost of Funds",
        "Weighted Average Cost of Funds", "WACF",
    ],
    "avg_cost_of_borrowing_pct": [
        "Average Cost of Borrowing", "Average Cost of Borrowings",
        "Avg Cost of Borrowing", "Avg Cost of Borrowings",
        "Average Borrowing Cost", "Average Borrowing Rate",
        "Weighted Average Cost of Borrowing", "WACB",
        "Cost of Borrowings %", "Borrowing Cost %",
    ],
    "lcr": [
        "LCR", "Liquidity Coverage Ratio", "Liquidity Ratio",
        "Liquid Coverage Ratio", "Liquidity Cover", "Liquidity Buffer Ratio",
        "High Quality Liquid Assets Ratio", "HQLA Ratio",
    ],
}


@dataclass(frozen=True)
class MappingMatch:
    """Audit record for a single field match."""

    standard_field: str
    method: str
    confidence: float
    matched_alias: str


def normalize_text(text: Any) -> str:
    """
    Normalize financial labels for deterministic matching.

    Handles case, punctuation, whitespace, common OCR artifacts, camel-case
    labels such as GrossStage3Assets, and Roman numeral stage disclosures.
    """
    if text is None:
        return ""

    normalized = str(text)
    normalized = re.sub(r"(?<=[a-z])(?=[A-Z0-9])", " ", normalized)
    normalized = normalized.lower().replace("&", " and ")
    normalized = normalized.replace("%", " percent ")
    normalized = re.sub(r"\(\s*percent\s*\)", " percent ", normalized)
    normalized = re.sub(r"\bn\s*\.?\s*p\s*\.?\s*a\.?\b", "npa", normalized)
    normalized = re.sub(r"\bc\s*\.?\s*r\s*\.?\s*a\s*\.?\s*r\.?\b", "crar", normalized)
    normalized = re.sub(r"\bc\s*\.?\s*a\s*\.?\s*r\.?\b", "car", normalized)
    normalized = re.sub(r"\bstage\s*[-]?\s*iii\b", "stage 3", normalized)
    normalized = re.sub(r"\bstage\s*[-]?\s*ii\b", "stage 2", normalized)
    normalized = re.sub(r"\bstage\s*[-]?\s*i\b", "stage 1", normalized)
    normalized = re.sub(r"\b(in|rs|inr|amount|amt)\s*(crores?|crs?|cr)\b", " ", normalized)
    normalized = re.sub(r"\b(crores?|crs?|cr|mn|million|bn|billion|lakh|lakhs)\b", " ", normalized)
    normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized


def exact_match(normalized_field: str) -> MappingMatch | None:
    """Match already-standardized field names first."""
    if normalized_field in _STANDARD_FIELD_LOOKUP:
        standard_field = _STANDARD_FIELD_LOOKUP[normalized_field]
        return MappingMatch(standard_field, "exact", 1.0, normalized_field)
    return None


def alias_match(normalized_field: str) -> MappingMatch | None:
    """Match normalized field labels against the enterprise alias dictionary."""
    if normalized_field in _ALIAS_LOOKUP:
        standard_field = _ALIAS_LOOKUP[normalized_field]
        return MappingMatch(standard_field, "alias", 1.0, normalized_field)
    return None


def fuzzy_match(normalized_field: str, threshold: int = FUZZY_THRESHOLD) -> MappingMatch | None:
    """Use RapidFuzz only after exact and alias matching fail."""
    result = process.extractOne(
        normalized_field,
        _NORMALIZED_ALIASES,
        scorer=fuzz.WRatio,
        score_cutoff=threshold,
    )
    if not result:
        return None

    matched_alias, score, _ = result
    return MappingMatch(
        standard_field=_ALIAS_LOOKUP[matched_alias],
        method="fuzzy",
        confidence=round(score / 100, 4),
        matched_alias=matched_alias,
    )


def calculate_mapping_confidence(
    match_records: list[MappingMatch],
    unmatched_count: int,
    total_fields: int,
) -> float:
    """
    Score confidence using direct-match ratio, fuzzy dependency, and misses.

    Exact/alias matches are strongest, fuzzy matches contribute their RapidFuzz
    score with a small dependency penalty, and unmatched fields reduce the
    final score.
    """
    if total_fields == 0:
        return 0.0

    matched_count = len(match_records)
    if matched_count == 0:
        return 0.0

    direct_count = sum(record.method in {"exact", "alias"} for record in match_records)
    fuzzy_count = sum(record.method == "fuzzy" for record in match_records)
    average_match_confidence = sum(record.confidence for record in match_records) / matched_count
    direct_match_ratio = direct_count / total_fields
    unmatched_penalty = unmatched_count / total_fields
    fuzzy_penalty = (fuzzy_count / total_fields) * 0.08

    confidence = (
        0.72 * average_match_confidence
        + 0.28 * direct_match_ratio
        - 0.18 * unmatched_penalty
        - fuzzy_penalty
    )
    return round(max(0.0, min(1.0, confidence)), 2)


def map_financial_line_items(data_dict: dict[str, Any]) -> dict[str, Any]:
    """
    Map extracted financial line items to standardized enterprise fields.

    Parameters
    ----------
    data_dict:
        Dictionary where keys are raw extracted labels and values are extracted
        financial values.

    Returns
    -------
    dict
        Structured mapping output with mapped values and audit metadata.
    """
    if not isinstance(data_dict, dict):
        raise TypeError("map_financial_line_items expects a dictionary input.")

    mapped_data: dict[str, Any] = {}
    unmatched_fields: list[str] = []
    suspicious_fields: list[dict[str, Any]] = []
    field_matches: dict[str, dict[str, Any]] = {}
    match_records: list[MappingMatch] = []
    populated_fields = 0

    for raw_field, value in data_dict.items():
        if _is_missing(value):
            continue

        populated_fields += 1
        normalized_field = normalize_text(raw_field)
        match = (
            exact_match(normalized_field)
            or alias_match(normalized_field)
            or fuzzy_match(normalized_field)
        )

        if match is None:
            unmatched_fields.append(str(raw_field))
            continue

        if match.confidence < LOW_CONFIDENCE_THRESHOLD:
            suspicious_fields.append(
                {
                    "field": str(raw_field),
                    "matched_to": match.standard_field,
                    "confidence": match.confidence,
                    "reason": "low_confidence_match",
                }
            )

        # Keep the first confident value for a canonical field to avoid later
        # noisy aliases overwriting an already-mapped disclosure.
        if match.standard_field not in mapped_data:
            mapped_data[match.standard_field] = value

        match_records.append(match)
        field_matches[str(raw_field)] = {
            "standard_field": match.standard_field,
            "method": match.method,
            "matched_alias": match.matched_alias,
            "confidence": match.confidence,
        }

    mapping_confidence = calculate_mapping_confidence(
        match_records=match_records,
        unmatched_count=len(unmatched_fields),
        total_fields=populated_fields,
    )

    mapping_metadata = {
        "matched_fields": len(match_records),
        "unmatched_fields": unmatched_fields,
        "suspicious_fields": suspicious_fields,
        "low_confidence_matches": suspicious_fields,
        "mapping_confidence": mapping_confidence,
        "field_matches": field_matches,
    }

    return {
        "mapped_data": mapped_data,
        "mapping_metadata": mapping_metadata,
        # Compatibility keys for earlier local smoke scripts.
        "unmatched_fields": unmatched_fields,
        "mapping_confidence": mapping_confidence,
        "mapping_details": field_matches,
    }


def get_standard_financial_fields() -> list[str]:
    """Return the supported standardized field names."""
    return sorted(FINANCIAL_MAPPING)


def _is_missing(value: Any) -> bool:
    """Treat None, NaN-like values, and blank strings as absent inputs."""
    if value is None:
        return True
    if isinstance(value, str) and value.strip() == "":
        return True
    return value != value


def _build_lookup_tables() -> tuple[dict[str, str], dict[str, str], list[str]]:
    standard_lookup: dict[str, str] = {}
    alias_lookup: dict[str, str] = {}

    for standard_field, aliases in FINANCIAL_MAPPING.items():
        standard_lookup[normalize_text(standard_field)] = standard_field
        for alias in aliases:
            alias_lookup[normalize_text(alias)] = standard_field

    all_aliases = sorted(set(alias_lookup))
    return standard_lookup, alias_lookup, all_aliases


_STANDARD_FIELD_LOOKUP, _ALIAS_LOOKUP, _NORMALIZED_ALIASES = _build_lookup_tables()


if __name__ == "__main__":
    sample_inputs = [
        {
            "AUM (Total)": 120000,
            "Profit After Tax": 3200,
            "Capital Adequacy Ratio": 22.5,
            "Gross Stage III Assets": 4200,
            "Deferred tax adjustment": 110,
        },
        {
            "GrossStage3Assets": 5100,
            "GROSS N.P.A.": 5200,
            "Revenue from Operations": 8400,
            "Interest / Finance Cost": 2100,
            "Net Interest Income": 3900,
            "Liquidity Coverage Ratio": 118,
        },
        {
            "Managed Assets": 95000,
            "Net Profit": 2800,
            "Tier-I Capital": 17.2,
            "Debt/Equity": 3.8,
            "Miscellaneous liabilities": 500,
        },
    ]

    for idx, sample in enumerate(sample_inputs, start=1):
        print(f"\nSample {idx}")
        print(map_financial_line_items(sample))
