import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.pdf_parser import extract_from_pdf
from src.financial_mapper import map_financial_line_items
from src.ratios import calculate_ratios

print("SCRIPT STARTED")

pdf_path = "data/sample_nbfc_report.pdf"

print("READING PDF...")

raw_output = extract_from_pdf(pdf_path)

print("PDF EXTRACTION COMPLETED")

print("\nRAW OUTPUT TYPE:")
print(type(raw_output))

if isinstance(raw_output, dict):

    print("\nRAW OUTPUT KEYS:")
    print(raw_output.keys())

    if "data" in raw_output:

        print("\n==============================")
        print("RAW EXTRACTED DATA")
        print("==============================")
        print(raw_output["data"])

        print("\n==============================")
        print("MAPPED DATA")
        print("==============================")

        mapped = map_financial_line_items(raw_output["data"])

        print(mapped["mapped_data"])

        print("\nUNMATCHED FIELDS:")
        print(mapped["mapping_metadata"]["unmatched_fields"])

        print("\nMAPPING CONFIDENCE:")
        print(mapped["mapping_metadata"]["mapping_confidence"])

        print("\n==============================")
        print("CALCULATED RATIOS")
        print("==============================")

        ratios = calculate_ratios(mapped["mapped_data"])

        print(ratios["calculated_ratios"])

        print("\nMISSING INPUTS:")
        print(ratios["ratio_metadata"]["missing_inputs"])

    else:
        print("\nNo 'data' key found.")

else:
    print("\nOutput is not a dictionary.")