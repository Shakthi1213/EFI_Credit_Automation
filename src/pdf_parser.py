
"""
pdf_parser.py
-------------
Extract financial data from PDF annual/quarterly reports and Excel files.

Strategy
--------
1. Try pdfplumber first (fast, text-based PDFs).
2. If a page yields little text, fall back to pytesseract OCR on a PIL image.
3. Use field_mapper to map extracted labels to standard field names.
4. Use utils.clean_numeric to parse values.

For Excel files:
- If the sheet is a wide, row-wise financial table (headers in row 1, values in row 2+),
  it converts the first meaningful data row into a standard dict.
- If the sheet is a key/value list, it falls back to label/value parsing.

Returns a dict of {standard_field: cleaned_value} plus metadata.
"""

import re
import io
import logging
from pathlib import Path

import pdfplumber
from .field_mapper import map_field, map_row_dict
from .utils import clean_numeric

logger = logging.getLogger(__name__)

# Minimum characters on a page before we consider it text-based
_MIN_TEXT_LEN = 80

# Heuristic: if an Excel sheet has this many or more columns, it's probably a wide table
_WIDE_TABLE_MIN_COLS = 8


def _normalize_col_name(name: str) -> str:
    """Normalize an Excel/PDF label into a safe snake_case-ish name."""
    s = str(name).strip().lower()
    s = s.replace("%", "_pct")
    s = s.replace("&", " and ")
    s = re.sub(r"[^\w\s]+", " ", s)
    s = re.sub(r"\s+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return s


def extract_from_pdf(pdf_path: str | Path) -> dict:
    """
    Main entry point.  Extracts financials from a PDF file.

    Returns
    -------
    dict with keys:
      - 'data'      : {standard_field: value}
      - 'raw_pairs' : [(raw_label, raw_value)] — before mapping
      - 'pages_used': number of pages parsed
      - 'method'    : 'text' | 'ocr' | 'mixed'
      - 'warnings'  : list of warning strings
    """
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        return _empty_result(f"File not found: {pdf_path}")

    raw_pairs = []
    pages_used = 0
    methods_used = set()
    warnings = []

    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page_num, page in enumerate(pdf.pages, start=1):
                text = page.extract_text() or ""

                if len(text.strip()) >= _MIN_TEXT_LEN:
                    # Good text layer
                    pairs = _parse_text_page(text)
                    methods_used.add("text")
                else:
                    # Scanned or image page — use OCR
                    pairs = _parse_ocr_page(page, page_num, warnings)
                    if pairs:
                        methods_used.add("ocr")

                # Also parse tables on each page
                try:
                    for table in page.extract_tables():
                        pairs += _parse_table(table)
                except Exception as e:
                    warnings.append(f"Table parse error p{page_num}: {e}")

                raw_pairs.extend(pairs)
                pages_used += 1

    except Exception as e:
        return _empty_result(f"PDF open error: {e}")

    mapped_data = _map_and_dedupe(raw_pairs)

    return {
        "data":       mapped_data,
        "raw_pairs":  raw_pairs,
        "pages_used": pages_used,
        "method":     "/".join(sorted(methods_used)) or "none",
        "warnings":   warnings,
    }


def _parse_text_page(text: str) -> list[tuple[str, str]]:
    """
    Extract (label, value) pairs from a text page using regex heuristics.
    """
    pairs = []
    lines = text.splitlines()

    for line in lines:
        # Pattern 1: "Label   Value"  (tab or multiple spaces)
        m = re.match(r"^([A-Za-z %/()&,-]{5,80}?)\s{2,}([\d,.()\-₹%\.]+\s*(?:Cr|Mn|Bn|Lakh|%)?)\s*$", line)
        if m:
            pairs.append((m.group(1).strip(), m.group(2).strip()))
            continue

        # Pattern 2: "Label: Value"
        m = re.match(r"^([A-Za-z %/()&,-]{5,80}):\s*([\d,.()\-₹%\.]+)", line)
        if m:
            pairs.append((m.group(1).strip(), m.group(2).strip()))

    return pairs


def _parse_ocr_page(page, page_num: int, warnings: list) -> list[tuple[str, str]]:
    """Rasterise page and run Tesseract OCR."""
    try:
        import pytesseract
        from PIL import Image
    except ImportError:
        warnings.append("pytesseract / Pillow not installed; OCR skipped")
        return []

    try:
        img = page.to_image(resolution=200).original
        text = pytesseract.image_to_string(img)
        return _parse_text_page(text)
    except Exception as e:
        warnings.append(f"OCR failed on page {page_num}: {e}")
        return []


def _parse_table(table: list[list]) -> list[tuple[str, str]]:
    """
    Extract (label, value) pairs from a pdfplumber table (list of rows).
    Assumes first column = label, second (or last non-empty) = value.
    """
    pairs = []
    if not table:
        return pairs

    for row in table:
        if not row or len(row) < 2:
            continue
        label = str(row[0] or "").strip()
        # pick first non-empty value after the label column
        value = None
        for cell in row[1:]:
            cell_str = str(cell or "").strip()
            if cell_str and cell_str not in ("-", "—", ""):
                value = cell_str
                break
        if label and value and len(label) > 2:
            pairs.append((label, value))

    return pairs


def _map_and_dedupe(raw_pairs: list[tuple[str, str]]) -> dict:
    """Map raw label→standard field, clean values, resolve duplicates (first wins)."""
    result = {}
    for label, raw_val in raw_pairs:
        std = map_field(label)
        if not std:
            continue
        if std in result:
            continue   # first occurrence wins
        cleaned = clean_numeric(raw_val)
        if cleaned is not None:
            result[std] = cleaned
        else:
            result[std] = raw_val   # keep as string if not numeric
    return result


def _empty_result(warning: str) -> dict:
    return {
        "data":       {},
        "raw_pairs":  [],
        "pages_used": 0,
        "method":     "none",
        "warnings":   [warning],
    }


# ─────────────────────────────────────────────────────────────────────────────
# Excel Extractor
# ─────────────────────────────────────────────────────────────────────────────

def extract_from_excel(file_path: str | Path, sheet_name: str | int = 0) -> dict:
    """
    Extract financial data from an Excel file.

    Supports two common layouts:

    1) Wide / tabular layout:
       - row 1 is the header row
       - each subsequent row is one company-period observation
       - used for model inputs / testing

    2) Long / key-value layout:
       - first column is label
       - second or later columns contain values
       - used by some extracted statements

    Returns same structure as extract_from_pdf.
    """
    import pandas as pd
    file_path = Path(file_path)
    warnings = []

    # Try reading as a normal table first (header row present)
    try:
        df = pd.read_excel(file_path, sheet_name=sheet_name)
    except Exception as e:
        return _empty_result(f"Excel read error: {e}")

    if df is None or df.empty:
        return _empty_result("Excel file is empty")

    # Clean column names
    original_columns = list(df.columns)
    norm_cols = [_normalize_col_name(c) for c in original_columns]
    df.columns = norm_cols

    # Determine whether this is a wide table or a key/value layout
    recognized_cols = 0
    for c in df.columns:
        if map_field(str(c)) is not None or c in {
            "company_name", "company_id", "quarter", "year", "sector",
            "external_rating", "rating_outlook", "rating_agency", "revenue",
            "pat", "pbt", "ebit", "ebitda", "interest_expense", "total_assets",
            "net_worth", "total_debt", "current_assets", "current_liabilities",
            "cash_and_bank", "aum", "roa", "roe", "debt_equity",
            "interest_coverage", "car", "gnpa_pct", "nnpa_pct",
            "pcr", "collection_efficiency", "liquidity_ratio", "leverage_ratio",
        }:
            recognized_cols += 1

    # ── Wide table mode: convert first meaningful row to a dict ──────────────
    if df.shape[1] >= _WIDE_TABLE_MIN_COLS or recognized_cols >= 4:
        # find the first non-empty row
        first_row = None
        for _, row in df.iterrows():
            if row.notna().sum() > 0:
                first_row = row
                break

        if first_row is None:
            return _empty_result("Excel contains headers but no data rows")

        row_dict = {}
        for col, val in first_row.to_dict().items():
            if pd.isna(val):
                continue

            # Prefer semantic mapping if possible; fallback to normalized column name
            std = map_field(str(col)) or _normalize_col_name(str(col))
            if not std:
                continue

            # clean numeric where possible; keep text for identifiers / rating fields
            if std in {
                "company_name", "company_id", "quarter", "year", "report_type",
                "sector", "sub_sector", "external_rating", "rating_outlook",
                "rating_agency", "rating_change", "risk_label", "news_sentiment",
            }:
                row_dict[std] = str(val).strip()
            else:
                cleaned = clean_numeric(val)
                row_dict[std] = cleaned if cleaned is not None else val

        # Ensure we keep original text values for key identifiers even if missing in map
        mapped_data = map_row_dict(row_dict)
        # map_row_dict can normalize/overwrite; restore better cleaned values
        mapped_data.update(row_dict)

        return {
            "data":       mapped_data,
            "raw_pairs":  list(row_dict.items()),
            "pages_used": len(df),
            "method":     "excel_wide",
            "warnings":   warnings,
        }

    # ── Key/value layout mode ─────────────────────────────────────────────────
    raw_pairs = []
    for _, row in df.iterrows():
        label = str(row.iloc[0] or "").strip()
        if not label or label.lower() in ("nan", "none", ""):
            continue
        # Use first non-NaN value in subsequent columns
        value = None
        for cell in row.iloc[1:]:
            if pd.notna(cell) and str(cell).strip() not in ("", "-", "—"):
                value = str(cell).strip()
                break
        if label and value:
            raw_pairs.append((label, value))

    mapped_data = _map_and_dedupe(raw_pairs)

    return {
        "data":       mapped_data,
        "raw_pairs":  raw_pairs,
        "pages_used": len(df),
        "method":     "excel_kv",
        "warnings":   warnings,
    }
