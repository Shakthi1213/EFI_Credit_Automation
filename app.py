"""
app.py
------
NBFC Credit Scoring System — Streamlit Dashboard

Pages:
  1. Single Company Analysis  — upload PDF/Excel, extract, score, show results
  2. Portfolio View           — upload the multi-NBFC Excel dataset
  3. Dataset Builder          — download the Excel template
  4. Methodology              — scorecard explanation
"""

import io
import tempfile
import json
import re
from pathlib import Path

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px

# ── local modules ────────────────────────────────────────────────────────────
from src.pdf_parser   import extract_from_pdf, extract_from_excel
from src.financial_mapper import map_financial_line_items
from src.ratios       import calculate_ratios, ratio_summary
from src.scoring      import score_nbfc
from src.flags        import get_flags, flags_to_text, SEVERITY_COLOR
from src.utils        import clean_numeric


# ─────────────────────────────────────────────────────────────────────────────
# Excel Column Cleaner
# ─────────────────────────────────────────────────────────────────────────────
def normalize_columns(df):
    """
    Cleans Excel column names so different formats work properly.
    """
    cleaned = []

    for col in df.columns:
        col = str(col).strip().lower()

        replacements = {
            "%": "_pct",
            "/": "_",
            " ": "_",
            "-": "_",
            "(": "",
            ")": "",
        }

        for old, new in replacements.items():
            col = col.replace(old, new)

        col = re.sub(r"_+", "_", col)

        cleaned.append(col)

    df.columns = cleaned
    return df


# ─────────────────────────────────────────────────────────────────────────────
# Page Config
# ─────────────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="NBFC Credit Scoring System",
    page_icon="🏦",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────────────────────────────────────
# Custom CSS
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
  @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@300;400;600;700&family=IBM+Plex+Mono&display=swap');

  html, body, [class*="css"] { font-family: 'IBM Plex Sans', sans-serif; }

  .metric-card {
    background: #0f1623;
    border: 1px solid #1e2d42;
    border-radius: 8px;
    padding: 16px 20px;
    text-align: center;
  }
  .metric-label { font-size: 11px; color: #7a8fa6; text-transform: uppercase; letter-spacing: 1px; }
  .metric-value { font-size: 28px; font-weight: 700; color: #e8f0fe; margin: 4px 0; }
  .metric-sub   { font-size: 12px; color: #556b82; }

  .risk-badge-Low      { background:#0a3d2b; color:#00e59a; border:1px solid #00e59a; padding:6px 16px; border-radius:20px; font-weight:700; display:inline-block; }
  .risk-badge-Moderate { background:#3d2a00; color:#ffb347; border:1px solid #ffb347; padding:6px 16px; border-radius:20px; font-weight:700; display:inline-block; }
  .risk-badge-High     { background:#3d1a00; color:#ff6b35; border:1px solid #ff6b35; padding:6px 16px; border-radius:20px; font-weight:700; display:inline-block; }
  .risk-badge-Critical { background:#3d0000; color:#ff4b4b; border:1px solid #ff4b4b; padding:6px 16px; border-radius:20px; font-weight:700; display:inline-block; }

  .flag-critical { color:#ff4b4b; font-size:13px; margin-bottom:4px; }
  .flag-warning  { color:#ffa500; font-size:13px; margin-bottom:4px; }
  .flag-info     { color:#4fa3e0; font-size:13px; margin-bottom:4px; }

  .section-header { font-size:13px; font-weight:600; color:#556b82; text-transform:uppercase; letter-spacing:1.5px; margin: 16px 0 8px 0; }
  .analyst-box { background:#080f1a; border-left:3px solid #4472c4; padding:16px; border-radius:4px; font-size:14px; line-height:1.7; color:#c5d3e8; }

  div[data-testid="stSidebar"] { background:#080f1a; border-right:1px solid #1e2d42; }
  .stButton>button { background:#1e3a5f; color:#e8f0fe; border:1px solid #2d5a8e; }
  .stButton>button:hover { background:#2d5a8e; }
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# Sidebar
# ─────────────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🏦 NBFC Credit\nScoring System")
    st.markdown("---")
    page = st.radio(
        "Navigate",
        ["Single Company Analysis", "Portfolio View", "Methodology"],
        label_visibility="collapsed",
    )
    st.markdown("---")
    st.markdown("<small style='color:#556b82'>EFI Credit Department<br>v1.0 — Rule-Based Scorecard</small>", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _gauge(score: float, title: str = "Credit Score") -> go.Figure:
    color = "#00e59a" if score >= 75 else "#ffb347" if score >= 55 else "#ff6b35" if score >= 35 else "#ff4b4b"
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=score,
        title={"text": title, "font": {"size": 14, "color": "#7a8fa6"}},
        gauge={
            "axis": {"range": [0, 100], "tickfont": {"color": "#556b82", "size": 10}},
            "bar":  {"color": color, "thickness": 0.25},
            "bgcolor": "#0f1623",
            "borderwidth": 0,
            "steps": [
                {"range": [0,  35], "color": "#1a0000"},
                {"range": [35, 55], "color": "#1a0d00"},
                {"range": [55, 75], "color": "#1a1400"},
                {"range": [75,100], "color": "#001a0e"},
            ],
        },
        number={"font": {"color": color, "size": 36}},
    ))
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        height=200, margin=dict(l=20, r=20, t=30, b=10),
    )
    return fig


def _pillar_bar(pillars) -> go.Figure:
    names  = [p.name for p in pillars]
    scores = [p.score for p in pillars]
    colors = ["#00e59a" if s >= 75 else "#ffb347" if s >= 55 else "#ff6b35" if s >= 35 else "#ff4b4b" for s in scores]

    fig = go.Figure(go.Bar(
        x=scores, y=names, orientation="h",
        marker_color=colors,
        text=[f"{s:.0f}" for s in scores],
        textposition="outside",
        textfont={"color": "#c5d3e8", "size": 11},
    ))
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(range=[0, 110], showgrid=False, zeroline=False, tickfont={"color": "#556b82"}),
        yaxis=dict(showgrid=False, tickfont={"color": "#c5d3e8", "size": 11}),
        height=260, margin=dict(l=10, r=30, t=10, b=10),
    )
    return fig


def _ratio_table(rows: list[dict]) -> None:
    signal_color = {"Good": "#00e59a", "Watch": "#ffb347", "Weak": "#ff4b4b"}
    cols = st.columns(len(rows))
    for col, row in zip(cols, rows):
        val = row["Value"]
        sig = row["Signal"]
        val_str = f"{val:.2f}" if isinstance(val, float) else (str(val) if val is not None else "—")
        col.markdown(
            f"""<div class="metric-card">
              <div class="metric-label">{row['Metric']}</div>
              <div class="metric-value" style="color:{signal_color.get(sig,'#c5d3e8')};font-size:20px">{val_str}</div>
              <div class="metric-sub">{sig}</div>
            </div>""",
            unsafe_allow_html=True,
        )


# ─────────────────────────────────────────────────────────────────────────────
# Page 1 — Single Company Analysis
# ─────────────────────────────────────────────────────────────────────────────


def page_single():
    st.markdown("## Single Company Credit Analysis")
    st.markdown(
        "<p style='color:#556b82'>Upload a PDF annual/quarterly report or Excel financial statement.</p>",
        unsafe_allow_html=True,
    )

    # ------------------------------------------------------------------
    # Session state defaults (safe: set before widgets are created)
    # ------------------------------------------------------------------
    defaults = {
        "company_name": "NBFC Ltd",
        "quarter": "Q3 FY25",
        "ext_rating": "AA",
        "sector": "HFC",
        "processed_file_name": None,
        "pending_metadata": None,
        "pending_metadata_for": None,
        "latest_extracted": None,
        "latest_result_meta": None,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

    sector_options = [
        "HFC",
        "MFI",
        "Gold Loan",
        "Auto Finance",
        "MSME Finance",
        "Consumer Finance",
        "Other",
    ]

    col_upload, col_meta = st.columns([2, 1])

    with col_upload:
        uploaded = st.file_uploader(
            "Upload Financial Statement",
            type=["pdf", "xlsx", "xls"],
            help="Text-based PDFs work best. Scanned PDFs use OCR (slower).",
            key="single_company_upload",
        )

    # ------------------------------------------------------------------
    # If a new file is uploaded, extract once and store metadata in
    # separate session keys. Then rerun so the widgets can read them
    # safely on the next pass.
    # ------------------------------------------------------------------
    if uploaded is not None:
        current_file = uploaded.name

        if st.session_state["processed_file_name"] != current_file:
            with st.spinner("Extracting financial data…"):
                suffix = Path(uploaded.name).suffix.lower()
                with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                    tmp.write(uploaded.read())
                    tmp_path = tmp.name

                if suffix == ".pdf":
                    result = extract_from_pdf(tmp_path)
                else:
                    result = extract_from_excel(tmp_path)

            mapping_result = map_financial_line_items(result["data"])
            extracted = mapping_result["mapped_data"] or {}

            # store results for the next pass
            st.session_state["latest_extracted"] = extracted
            st.session_state["latest_result_meta"] = {
                "method": result.get("method", "Unknown"),
                "pages_used": result.get("pages_used", "—"),
                "warnings": result.get("warnings", []),
                "mapping_confidence": mapping_result.get("mapping_confidence", 0.0),
                "unmatched_fields": mapping_result.get("unmatched_fields", []),
                "mapping_details": mapping_result.get("mapping_details", {}),
            }

            st.session_state["pending_metadata"] = {
                "company_name": extracted.get("company_name", st.session_state["company_name"]),
                "quarter": extracted.get("quarter", st.session_state["quarter"]),
                "ext_rating": extracted.get("external_rating", st.session_state["ext_rating"]),
                "sector": extracted.get("sector", st.session_state["sector"]),
            }
            st.session_state["pending_metadata_for"] = current_file
            st.session_state["processed_file_name"] = current_file

            # rerun so the widgets pick up the extracted values
            st.rerun()

        # Apply pending metadata before widgets are created.
        if (
            st.session_state.get("pending_metadata_for") == current_file
            and st.session_state.get("pending_metadata")
        ):
            pending = st.session_state["pending_metadata"]
            st.session_state["company_name"] = pending.get("company_name", st.session_state["company_name"])
            st.session_state["quarter"] = pending.get("quarter", st.session_state["quarter"])
            st.session_state["ext_rating"] = pending.get("ext_rating", st.session_state["ext_rating"])
            st.session_state["sector"] = pending.get("sector", st.session_state["sector"])

            # clear pending state after applying
            st.session_state["pending_metadata"] = None
            st.session_state["pending_metadata_for"] = None

    with col_meta:
        company_name = st.text_input("Company Name", key="company_name")
        quarter = st.text_input("Quarter / Period", key="quarter")
        ext_rating = st.text_input("External Rating (optional)", key="ext_rating")

        sector_index = sector_options.index(st.session_state["sector"]) if st.session_state["sector"] in sector_options else 0
        sector = st.selectbox(
            "Sector",
            sector_options,
            index=sector_index,
            key="sector",
        )

    if uploaded is None:
        st.info("Upload a file or use the manual entry form below.")
        _manual_entry_form(company_name, quarter, ext_rating)
        return

    # ------------------------------------------------------------------
    # Use extracted data if present; otherwise fall back gracefully.
    # ------------------------------------------------------------------
    extracted = st.session_state.get("latest_extracted") or {}
    result_meta = st.session_state.get("latest_result_meta") or {
        "method": "Unknown",
        "pages_used": "—",
        "warnings": [],
        "mapping_confidence": 0.0,
        "unmatched_fields": [],
        "mapping_details": {},
    }

    # If the uploaded file did not contain these fields, keep the manual
    # values from the widgets.
    extracted["company_name"] = company_name
    extracted["external_rating"] = ext_rating
    extracted["quarter"] = quarter
    extracted["sector"] = sector

    # ── Status ───────────────────────────────────────────────────────────────
    with st.expander("📄 Extraction Status", expanded=False):
        st.write(f"**Method:** {result_meta['method']}  |  **Pages/Rows:** {result_meta['pages_used']}")
        st.write(f"**Mapping confidence:** {result_meta.get('mapping_confidence', 0.0):.2f}")
        if result_meta["warnings"]:
            for w in result_meta["warnings"]:
                st.warning(w)
        st.write(f"**Mapped fields:** {len(extracted)}")
        if extracted:
            st.dataframe(
                pd.DataFrame(list(extracted.items()), columns=["Field", "Value"]),
                use_container_width=True,
            )
        unmatched_fields = result_meta.get("unmatched_fields", [])
        if unmatched_fields:
            st.write("**Unmapped fields:**")
            st.write(unmatched_fields)

    _run_analysis(extracted, company_name, quarter)


def _manual_entry_form(company_name: str, quarter: str, ext_rating: str):
    """Fallback manual data entry form."""
    st.markdown("### ✏️ Manual Data Entry")
    st.markdown("<p style='color:#556b82;font-size:13px'>Enter key financial figures below (₹ Crores unless noted).</p>", unsafe_allow_html=True)

    with st.form("manual_entry"):
        c1, c2, c3 = st.columns(3)
        data = {}
        fields_labels = [
            ("revenue", "Revenue / Total Income"),
            ("pat", "PAT / Net Profit"),
            ("ebit", "EBIT"),
            ("interest_expense", "Interest Expense"),
            ("total_assets", "Total Assets"),
            ("net_worth", "Net Worth"),
            ("total_debt", "Total Debt / Borrowings"),
            ("current_assets", "Current Assets"),
            ("current_liabilities", "Current Liabilities"),
            ("cash_and_bank", "Cash & Bank"),
            ("aum", "AUM / Loan Book"),
            ("gnpa_pct", "GNPA (%)"),
            ("nnpa_pct", "NNPA (%)"),
            ("pcr", "PCR (%)"),
            ("car", "CAR / CRAR (%)"),
            ("collection_efficiency", "Collection Efficiency (%)"),
        ]
        cols = [c1, c2, c3]
        for i, (field, label) in enumerate(fields_labels):
            val = cols[i % 3].text_input(label, key=f"mf_{field}", placeholder="e.g. 1234.56")
            if val.strip():
                cleaned = clean_numeric(val)
                if cleaned is not None:
                    data[field] = cleaned

        governance_expander = st.expander("Governance Flags (optional)")
        with governance_expander:
            gc1, gc2, gc3 = st.columns(3)
            if gc1.checkbox("Auditor Change"):    data["auditor_change_flag"]    = 1
            if gc2.checkbox("Management Change"): data["management_change_flag"] = 1
            if gc3.checkbox("Regulatory Issue"):  data["regulatory_issue_flag"]  = 1
            pledge = gc1.text_input("Promoter Pledge %", "0")
            if pledge:
                try: data["promoter_pledge_pct"] = float(pledge)
                except: pass

        submitted = st.form_submit_button("▶ Run Analysis", use_container_width=True)

    if submitted and data:
        data["external_rating"] = ext_rating
        _run_analysis(data, company_name, quarter)
    elif submitted:
        st.warning("Please enter at least some financial data.")


def _run_analysis(data: dict, company_name: str, quarter: str):
    """Common analysis pipeline."""
    enriched = calculate_ratios(data)
    result   = score_nbfc(enriched, company_name, quarter)
    flags    = get_flags(enriched)

    # ── Score Banner ─────────────────────────────────────────────────────────
    st.markdown("---")
    b_col, g_col, r_col = st.columns([1, 1, 2])

    badge_key = result.risk_category.split()[0]   # "Low" / "Moderate" / "High" / "Critical"
    b_col.markdown(
        f"<div style='padding-top:30px'>"
        f"<div class='risk-badge-{badge_key}'>{result.risk_category}</div>"
        f"<div style='font-size:30px;font-weight:700;color:#e8f0fe;margin-top:10px'>{result.total_score:.1f}<span style='font-size:16px;color:#556b82'>/100</span></div>"
        f"<div style='color:#7a8fa6;font-size:12px'>{company_name} · {quarter}</div>"
        f"</div>",
        unsafe_allow_html=True,
    )
    g_col.plotly_chart(_gauge(result.total_score), use_container_width=True)

    with r_col:
        st.markdown("<div class='section-header'>Red Flags</div>", unsafe_allow_html=True)
        if result.red_flags:
            for f in result.red_flags:
                st.markdown(f"<div class='flag-critical'>{f}</div>", unsafe_allow_html=True)
        else:
            st.markdown("<div style='color:#00e59a;font-size:13px'>✅ No critical red flags detected</div>", unsafe_allow_html=True)

    # ── Pillar Breakdown ─────────────────────────────────────────────────────
    st.markdown("---")
    p_col, r_col2 = st.columns([1, 1])
    with p_col:
        st.markdown("<div class='section-header'>Pillar Scores</div>", unsafe_allow_html=True)
        st.plotly_chart(_pillar_bar(result.pillars), use_container_width=True)

    with r_col2:
        st.markdown("<div class='section-header'>Pillar Details</div>", unsafe_allow_html=True)
        for pillar in result.pillars:
            with st.expander(f"{pillar.name}  ({pillar.score:.0f}/100)"):
                for reason in pillar.reasons:
                    st.markdown(f"<small>• {reason}</small>", unsafe_allow_html=True)

    # ── Key Ratios ───────────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("<div class='section-header'>Key Ratios</div>", unsafe_allow_html=True)
    rows = ratio_summary(enriched)
    _ratio_table(rows[:5])
    st.markdown("<div style='margin-top:8px'></div>", unsafe_allow_html=True)
    _ratio_table(rows[5:])

    # ── Analyst Summary ───────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("<div class='section-header'>Analyst Summary</div>", unsafe_allow_html=True)
    st.markdown(f"<div class='analyst-box'>{result.analyst_summary.replace(chr(10),'<br>')}</div>", unsafe_allow_html=True)

    # ── Full Data ─────────────────────────────────────────────────────────────
    with st.expander("📊 Full Extracted & Computed Data"):
        df_out = pd.DataFrame(list(enriched.items()), columns=["Field", "Value"])
        st.dataframe(df_out, use_container_width=True)

    # ── Export JSON ───────────────────────────────────────────────────────────
    export_data = {
        "company": company_name, "quarter": quarter,
        "score": result.total_score, "risk_category": result.risk_category,
        "pillars": {p.name: p.score for p in result.pillars},
        "red_flags": result.red_flags, "data": enriched,
    }
    st.download_button(
        "⬇ Export as JSON",
        data=json.dumps(export_data, indent=2, default=str),
        file_name=f"{company_name.replace(' ','_')}_{quarter}_credit_report.json",
        mime="application/json",
    )


# ─────────────────────────────────────────────────────────────────────────────
# Page 2 — Portfolio View
# ─────────────────────────────────────────────────────────────────────────────

def page_portfolio():
    st.markdown("## Portfolio Credit Dashboard")
    st.markdown("<p style='color:#556b82'>Upload your multi-NBFC panel dataset (Excel). Each row = one company × one quarter.</p>", unsafe_allow_html=True)

    uploaded = st.file_uploader("Upload NBFC Dataset Excel", type=["xlsx", "xls"])

    if not uploaded:
        st.info("Download the template from the **Dataset Builder** tab, fill it in, and upload here.")
        return

    try:
        df = pd.read_excel(uploaded, sheet_name="raw_data")
        df = normalize_columns(df)
    except Exception:
        try:
            df = pd.read_excel(uploaded)
            df = normalize_columns(df)
        except Exception as e:
            st.error(f"Could not read file: {e}")
            return

    st.success(f"Loaded {len(df)} rows × {len(df.columns)} columns")

    # ── Score all rows ────────────────────────────────────────────────────────
    results = []
    numeric_cols = [c for c in df.columns if c not in ("company_name","quarter","year","sector","external_rating","report_type","source_file","rating_outlook","rating_agency","sub_sector","news_sentiment","risk_label","rating_change")]

    for _, row in df.iterrows():
        row_dict = row.to_dict()
        for col in numeric_cols:
            if col in row_dict:
                row_dict[col] = clean_numeric(str(row_dict[col])) if pd.notna(row_dict.get(col)) else None
        enriched = calculate_ratios(row_dict)
        sr = score_nbfc(enriched,
                        company_name=str(row_dict.get("company_name", "Unknown")),
                        quarter=str(row_dict.get("quarter", "")))
        results.append({
            "Company":       sr.company_name,
            "Quarter":       sr.quarter,
            "Score":         sr.total_score,
            "Risk Category": sr.risk_category,
            "Red Flags":     len(sr.red_flags),
        })

    res_df = pd.DataFrame(results)

    # ── Summary metrics ───────────────────────────────────────────────────────
    m1, m2, m3, m4 = st.columns(4)
    risk_counts = res_df["Risk Category"].value_counts()
    m1.metric("Total NBFCs", len(res_df["Company"].unique()))
    m2.metric("Critical / High Risk", risk_counts.get("Critical Risk",0) + risk_counts.get("High Risk",0))
    m3.metric("Avg Credit Score", f"{res_df['Score'].mean():.1f}")
    m4.metric("With Red Flags", int((res_df["Red Flags"] > 0).sum()))

    # ── Distribution chart ────────────────────────────────────────────────────
    c1, c2 = st.columns(2)
    with c1:
        pie = px.pie(
            res_df, names="Risk Category",
            color="Risk Category",
            color_discrete_map={
                "Low Risk":"#00e59a","Moderate Risk":"#ffb347",
                "High Risk":"#ff6b35","Critical Risk":"#ff4b4b",
            },
            title="Risk Category Distribution",
        )
        pie.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font_color="#c5d3e8")
        st.plotly_chart(pie, use_container_width=True)

    with c2:
        bar = px.bar(
            res_df.sort_values("Score"),
            x="Score", y="Company", orientation="h",
            color="Score", color_continuous_scale=["#ff4b4b","#ff6b35","#ffb347","#00e59a"],
            title="Credit Score Ranking",
        )
        bar.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font_color="#c5d3e8", height=max(250, len(res_df)*25))
        st.plotly_chart(bar, use_container_width=True)

    # ── Table ─────────────────────────────────────────────────────────────────
    st.markdown("### Company Scores")
    st.dataframe(
    res_df.sort_values("Score"),
    use_container_width=True,
)

    # ── Download results ──────────────────────────────────────────────────────
    csv = res_df.to_csv(index=False)
    st.download_button("⬇ Download Scores CSV", csv, "nbfc_portfolio_scores.csv", "text/csv")


# ─────────────────────────────────────────────────────────────────────────────
# Page 4 — Methodology
# ─────────────────────────────────────────────────────────────────────────────

def page_methodology():
    st.markdown("## Scoring Methodology")

    st.markdown("""
<div style='background:#080f1a;border:1px solid #1e2d42;border-radius:8px;padding:24px;line-height:1.8;color:#c5d3e8'>

<h4 style='color:#e8f0fe'>Six-Pillar Scorecard</h4>

Each NBFC is evaluated across six pillars. Each pillar is scored 0–100 and
weighted to produce a final composite score out of 100.

<table style='width:100%;margin-top:12px;border-collapse:collapse;font-size:13px'>
<tr style='border-bottom:1px solid #1e2d42'>
  <th style='text-align:left;color:#7a8fa6;padding:6px'>Pillar</th>
  <th style='text-align:left;color:#7a8fa6;padding:6px'>Weight</th>
  <th style='text-align:left;color:#7a8fa6;padding:6px'>Key Metrics</th>
</tr>
<tr><td style='padding:6px'>Profitability</td><td>20%</td><td>ROA, ROE, PAT Growth</td></tr>
<tr style='background:#0a1220'><td style='padding:6px'>Asset Quality</td><td>25%</td><td>GNPA%, NNPA%, PCR, Collection Efficiency</td></tr>
<tr><td style='padding:6px'>Leverage & Capital</td><td>20%</td><td>D/E Ratio, CAR, Leverage Ratio</td></tr>
<tr style='background:#0a1220'><td style='padding:6px'>Liquidity</td><td>20%</td><td>Current Ratio, Interest Coverage, Cash Ratio</td></tr>
<tr><td style='padding:6px'>Growth</td><td>5%</td><td>AUM Growth YoY, Revenue Growth YoY</td></tr>
<tr style='background:#0a1220'><td style='padding:6px'>Governance & Rating</td><td>10%</td><td>External Rating, Auditor/Mgmt Flags, Pledge %</td></tr>
</table>

<h4 style='color:#e8f0fe;margin-top:20px'>Risk Categories</h4>
<table style='width:100%;border-collapse:collapse;font-size:13px'>
<tr style='border-bottom:1px solid #1e2d42'><th style='text-align:left;color:#7a8fa6;padding:6px'>Score Range</th><th style='text-align:left;color:#7a8fa6;padding:6px'>Category</th><th style='text-align:left;color:#7a8fa6;padding:6px'>Action</th></tr>
<tr><td style='padding:6px;color:#00e59a'>75 – 100</td><td>Low Risk</td><td>Standard monitoring</td></tr>
<tr style='background:#0a1220'><td style='padding:6px;color:#ffb347'>55 – 74</td><td>Moderate Risk</td><td>Enhanced quarterly review</td></tr>
<tr><td style='padding:6px;color:#ff6b35'>35 – 54</td><td>High Risk</td><td>Credit committee escalation</td></tr>
<tr style='background:#0a1220'><td style='padding:6px;color:#ff4b4b'>0 – 34</td><td>Critical Risk</td><td>Immediate review, consider exit</td></tr>
</table>

</div>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# Router
# ─────────────────────────────────────────────────────────────────────────────
if page == "Single Company Analysis":
    page_single()
elif page == "Portfolio View":
    page_portfolio()
elif page == "Methodology":
    page_methodology()
