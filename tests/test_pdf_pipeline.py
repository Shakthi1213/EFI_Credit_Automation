print("SCRIPT STARTED")
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src.pdf_parser import extract_from_pdf
from src.financial_mapper import (
    build_financial_extraction_report,
    clean_financial_data,
    map_financial_line_items,
)
from src.ratios import calculate_ratios

# Put your PDF file path here
pdf_path = "data/sample_nbfc_report.pdf"

# STEP 1 — Extract from PDF
raw_data = extract_from_pdf(pdf_path)

print("\n==============================")
print("RAW EXTRACTED DATA")
print("==============================")

for k, v in raw_data.items():
    print(f"{k}: {v}")

# STEP 2 — Map financial fields
mapped = map_financial_line_items(raw_data)

print("\n==============================")
print("MAPPED DATA")
print("==============================")

print(mapped["mapped_data"])

print("\nUNMATCHED FIELDS:")
print(mapped["mapping_metadata"]["unmatched_fields"])

# STEP 3 — Calculate ratios
ratios = calculate_ratios(mapped["mapped_data"])

print("\n==============================")
print("CALCULATED RATIOS")
print("==============================")

print(ratios["calculated_ratios"])

print("\nMISSING INPUTS:")
print(ratios["ratio_metadata"]["missing_inputs"])


def test_mapper_uses_pdf_wrapper_data_only():
    raw_output = {
        "data": {
            "AUM": "259.48 bn",
            "Profit After Tax": "5,313.98 mn",
            "Capital Adequacy Ratio": "25.42%",
        },
        "raw_pairs": [("AUM", "259.48 bn")],
        "pages_used": [1],
        "method": "text",
        "warnings": [],
    }

    cleaned = clean_financial_data(raw_output)
    mapped_result = map_financial_line_items(raw_output)
    report = build_financial_extraction_report(raw_output)
    ratio_result = calculate_ratios(mapped_result["mapped_data"])

    assert set(cleaned) == {"AUM", "Profit After Tax", "Capital Adequacy Ratio"}
    assert mapped_result["mapped_data"]["aum_total"] == 25948.0
    assert mapped_result["mapped_data"]["pat"] == 531.398
    assert mapped_result["mapped_data"]["car_pct"] == 25.42
    assert not {"data", "raw_pairs", "pages_used", "method", "warnings"} & set(
        mapped_result["unmatched_fields"]
    )
    assert ratio_result["calculated_ratios"]["car_pct"] == 25.42
    assert set(report) >= {"mapped_data", "unmapped_fields", "confidence_score", "ratios"}
