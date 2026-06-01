# EFI Credit Automation

AI-Based NBFC Credit Intelligence & Early Warning Platform.

This project supports NBFC credit underwriting, portfolio monitoring, and early warning detection through a Streamlit dashboard, credit scoring engine, financial mapping layer, ratio calculations, and red flag analytics.

## Current Capabilities

- Streamlit credit dashboard
- Portfolio dashboard
- Credit scoring and risk categorization
- Red flag detection
- Upload and Excel extraction workflow
- Financial line-item standardization
- Core NBFC ratio calculation layer

## Financial Intelligence Layer

The financial intelligence layer standardizes inconsistent NBFC financial terminology and calculates reusable credit ratios for scoring, trend analysis, regulatory checks, peer benchmarking, and future model development.

Key modules:

- `src/financial_mapper.py`: maps raw financial labels to standard internal fields using exact, alias, and fuzzy matching.
- `src/ratios.py`: calculates ROA, ROE, debt/equity, interest coverage, GNPA %, NNPA %, leverage, and liquidity ratios safely.
- `tests/test_ratios.py`: smoke script that maps the sample Excel dataset, calculates ratios, prints confidence outputs, and writes `ratio_output.xlsx`.

## Setup

```powershell
pip install -r requirements.txt
```

## Run The Dashboard

```powershell
streamlit run app.py
```

## Run The Ratio Smoke Test

```powershell
python tests/test_ratios.py
```

## Project Structure

```text
EFI_Credit_Automation/
  app.py
  requirements.txt
  data/
  src/
    field_mapper.py
    financial_mapper.py
    flags.py
    pdf_parser.py
    ratios.py
    scoring.py
    utils.py
  tests/
    test_ratios.py
```
