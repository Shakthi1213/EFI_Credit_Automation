"""
Smoke script for the Financial Intelligence Layer.

Loads the sample Excel dataset, maps inconsistent financial labels to standard
fields, calculates core NBFC ratios, prints audit-friendly outputs, and saves
the consolidated result to ratio_output.xlsx.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.financial_mapper import map_financial_line_items
from src.ratios import calculate_ratios


INPUT_FILE = PROJECT_ROOT / "data" / "NBFC_Phase1_Mapped_Dataset_Updated.xlsx"
OUTPUT_FILE = PROJECT_ROOT / "ratio_output.xlsx"


def run_ratio_smoke_test() -> pd.DataFrame:
    df = pd.read_excel(INPUT_FILE)
    output_rows: list[dict] = []

    for idx, row in df.iterrows():
        raw_dict = row.dropna().to_dict()
        mapping_result = map_financial_line_items(raw_dict)
        ratio_result = calculate_ratios(mapping_result["mapped_data"])

        print(f"\nRow {idx + 1}")
        print("Mapped fields:", mapping_result["mapped_data"])
        print("Unmatched fields:", mapping_result["unmatched_fields"])
        print("Calculated ratios:", ratio_result["calculated_ratios"])
        print("Mapping confidence:", mapping_result["mapping_confidence"])
        print("Calculation confidence:", ratio_result["calculation_confidence"])

        output_rows.append(
            {
                "row_number": idx + 1,
                **mapping_result["mapped_data"],
                **ratio_result["calculated_ratios"],
                "unmatched_fields": ", ".join(mapping_result["unmatched_fields"]),
                "mapping_confidence": mapping_result["mapping_confidence"],
                "calculation_confidence": ratio_result["calculation_confidence"],
            }
        )

    output_df = pd.DataFrame(output_rows)
    output_df.to_excel(OUTPUT_FILE, index=False)
    print(f"\nSaved ratio output to: {OUTPUT_FILE}")
    return output_df


if __name__ == "__main__":
    run_ratio_smoke_test()
