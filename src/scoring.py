"""
scoring.py
----------
Rule-based credit scorecard for NBFCs.

Design
------
Six pillars, each worth up to 100 points. A weighted average gives the
final score out of 100.  Score → Risk Category:

  ≥ 75  →  Low Risk     (Green)
  55–74 →  Moderate Risk (Yellow)
  35–54 →  High Risk     (Orange)
  < 35  →  Critical Risk (Red)

Each pillar returns:
  - pillar_score  : 0–100
  - reason_codes  : list of explanation strings

The function returns a full ScoreResult dataclass.
"""

from dataclasses import dataclass, field


@dataclass
class PillarResult:
    name: str
    score: float          # 0–100
    weight: float         # contribution weight
    reasons: list[str] = field(default_factory=list)


@dataclass
class ScoreResult:
    company_name: str
    quarter: str
    total_score: float            # 0–100
    risk_category: str            # Low / Moderate / High / Critical
    risk_color: str               # green / yellow / orange / red
    pillars: list[PillarResult] = field(default_factory=list)
    red_flags: list[str]          = field(default_factory=list)
    analyst_summary: str          = ""


# ─────────────────────────────────────────────────────────────────────────────
# Pillar 1 – Profitability
# ─────────────────────────────────────────────────────────────────────────────

def _score_profitability(d: dict) -> PillarResult:
    score = 0
    reasons = []

    roa = d.get("roa")
    roe = d.get("roe")
    pat_growth = d.get("pat_growth_yoy")

    if roa is not None:
        if roa >= 2.5:   score += 40; reasons.append(f"Strong ROA: {roa:.1f}%")
        elif roa >= 1.5: score += 30; reasons.append(f"Adequate ROA: {roa:.1f}%")
        elif roa >= 0.5: score += 15; reasons.append(f"Thin ROA: {roa:.1f}%")
        else:            score += 0;  reasons.append(f"Weak ROA: {roa:.1f}%")
    else:
        reasons.append("ROA not available")

    if roe is not None:
        if roe >= 15:    score += 40; reasons.append(f"Strong ROE: {roe:.1f}%")
        elif roe >= 10:  score += 30; reasons.append(f"Moderate ROE: {roe:.1f}%")
        elif roe >= 5:   score += 15; reasons.append(f"Low ROE: {roe:.1f}%")
        else:            score += 0;  reasons.append(f"Very low ROE: {roe:.1f}%")
    else:
        reasons.append("ROE not available")

    if pat_growth is not None:
        if pat_growth >= 15:   score += 20; reasons.append(f"PAT growth {pat_growth:.1f}% YoY – strong")
        elif pat_growth >= 5:  score += 12; reasons.append(f"PAT growth {pat_growth:.1f}% YoY – moderate")
        elif pat_growth >= 0:  score += 5;  reasons.append(f"PAT growth flat {pat_growth:.1f}%")
        else:                  score += 0;  reasons.append(f"PAT declined {pat_growth:.1f}% YoY")

    return PillarResult("Profitability", min(score, 100), weight=0.20, reasons=reasons)


# ─────────────────────────────────────────────────────────────────────────────
# Pillar 2 – Asset Quality
# ─────────────────────────────────────────────────────────────────────────────

def _score_asset_quality(d: dict) -> PillarResult:
    score = 0
    reasons = []

    gnpa = d.get("gnpa_pct")
    nnpa = d.get("nnpa_pct")
    pcr  = d.get("pcr")
    ce   = d.get("collection_efficiency")

    if gnpa is not None:
        if gnpa < 2:    score += 35; reasons.append(f"GNPA very low: {gnpa:.1f}%")
        elif gnpa < 4:  score += 25; reasons.append(f"GNPA manageable: {gnpa:.1f}%")
        elif gnpa < 7:  score += 12; reasons.append(f"GNPA elevated: {gnpa:.1f}%")
        else:           score += 0;  reasons.append(f"GNPA high: {gnpa:.1f}%")
    else:
        reasons.append("GNPA not available")

    if nnpa is not None:
        if nnpa < 1:    score += 25; reasons.append(f"NNPA low: {nnpa:.1f}%")
        elif nnpa < 2:  score += 18; reasons.append(f"NNPA moderate: {nnpa:.1f}%")
        elif nnpa < 4:  score += 8;  reasons.append(f"NNPA elevated: {nnpa:.1f}%")
        else:           score += 0;  reasons.append(f"NNPA high: {nnpa:.1f}%")
    else:
        reasons.append("NNPA not available")

    if pcr is not None:
        if pcr >= 70:   score += 25; reasons.append(f"Strong provision coverage: {pcr:.0f}%")
        elif pcr >= 50: score += 15; reasons.append(f"Adequate PCR: {pcr:.0f}%")
        elif pcr >= 35: score += 8;  reasons.append(f"Low PCR: {pcr:.0f}%")
        else:           score += 0;  reasons.append(f"Very low PCR: {pcr:.0f}%")
    else:
        reasons.append("PCR not available")

    if ce is not None:
        if ce >= 98:    score += 15; reasons.append(f"Excellent collection efficiency: {ce:.1f}%")
        elif ce >= 95:  score += 10; reasons.append(f"Good collection efficiency: {ce:.1f}%")
        elif ce >= 90:  score += 5;  reasons.append(f"Collection efficiency declining: {ce:.1f}%")
        else:           score += 0;  reasons.append(f"Poor collection efficiency: {ce:.1f}%")

    return PillarResult("Asset Quality", min(score, 100), weight=0.25, reasons=reasons)


# ─────────────────────────────────────────────────────────────────────────────
# Pillar 3 – Leverage & Capital Structure
# ─────────────────────────────────────────────────────────────────────────────

def _score_leverage(d: dict) -> PillarResult:
    score = 0
    reasons = []

    de    = d.get("debt_equity")
    lev   = d.get("leverage_ratio")
    car   = d.get("car")

    if de is not None:
        if de <= 3:    score += 40; reasons.append(f"Conservative leverage D/E: {de:.1f}x")
        elif de <= 5:  score += 28; reasons.append(f"Moderate leverage D/E: {de:.1f}x")
        elif de <= 7:  score += 14; reasons.append(f"High leverage D/E: {de:.1f}x")
        else:          score += 0;  reasons.append(f"Very high leverage D/E: {de:.1f}x")
    else:
        reasons.append("D/E ratio not available")

    if car is not None:
        if car >= 20:  score += 40; reasons.append(f"Strong CAR: {car:.1f}%")
        elif car >= 15: score += 30; reasons.append(f"Adequate CAR: {car:.1f}%")
        elif car >= 12: score += 15; reasons.append(f"CAR near minimum: {car:.1f}%")
        else:           score += 0;  reasons.append(f"CAR below threshold: {car:.1f}%")
    else:
        reasons.append("CAR not available")

    if lev is not None:
        if lev <= 5:   score += 20; reasons.append(f"Low leverage: {lev:.1f}x assets/equity")
        elif lev <= 7: score += 12; reasons.append(f"Moderate leverage: {lev:.1f}x")
        elif lev <= 9: score += 5;  reasons.append(f"High leverage: {lev:.1f}x")
        else:          score += 0;  reasons.append(f"Very high leverage: {lev:.1f}x")

    return PillarResult("Leverage & Capital", min(score, 100), weight=0.20, reasons=reasons)


# ─────────────────────────────────────────────────────────────────────────────
# Pillar 4 – Liquidity
# ─────────────────────────────────────────────────────────────────────────────

def _score_liquidity(d: dict) -> PillarResult:
    score = 0
    reasons = []

    cr       = d.get("liquidity_ratio")
    ic       = d.get("interest_coverage")
    cash_rat = d.get("cash_ratio")

    if cr is not None:
        if cr >= 1.5:   score += 40; reasons.append(f"Strong current ratio: {cr:.2f}x")
        elif cr >= 1.2: score += 28; reasons.append(f"Adequate current ratio: {cr:.2f}x")
        elif cr >= 1.0: score += 12; reasons.append(f"Tight current ratio: {cr:.2f}x")
        else:           score += 0;  reasons.append(f"Current ratio below 1: {cr:.2f}x")
    else:
        reasons.append("Current ratio not available")

    if ic is not None:
        if ic >= 3:    score += 40; reasons.append(f"Strong interest coverage: {ic:.1f}x")
        elif ic >= 2:  score += 28; reasons.append(f"Adequate interest coverage: {ic:.1f}x")
        elif ic >= 1.2: score += 14; reasons.append(f"Thin interest coverage: {ic:.1f}x")
        else:          score += 0;  reasons.append(f"Insufficient interest coverage: {ic:.1f}x")
    else:
        reasons.append("Interest coverage not available")

    if cash_rat is not None:
        if cash_rat >= 0.5: score += 20; reasons.append(f"Strong cash buffer")
        elif cash_rat >= 0.2: score += 12; reasons.append(f"Moderate cash buffer")
        else:                 score += 4;  reasons.append(f"Low cash buffer")

    return PillarResult("Liquidity", min(score, 100), weight=0.15, reasons=reasons)


# ─────────────────────────────────────────────────────────────────────────────
# Pillar 5 – Growth & Business Momentum
# ─────────────────────────────────────────────────────────────────────────────

def _score_growth(d: dict) -> PillarResult:
    score = 0
    reasons = []

    aum_g = d.get("aum_growth_yoy")
    rev_g = d.get("revenue_growth_yoy")

    if aum_g is not None:
        if aum_g >= 25:   score += 50; reasons.append(f"Strong AUM growth: {aum_g:.1f}% YoY")
        elif aum_g >= 15: score += 35; reasons.append(f"Good AUM growth: {aum_g:.1f}% YoY")
        elif aum_g >= 5:  score += 20; reasons.append(f"Moderate AUM growth: {aum_g:.1f}%")
        elif aum_g >= 0:  score += 10; reasons.append(f"Flat AUM growth: {aum_g:.1f}%")
        else:             score += 0;  reasons.append(f"AUM contraction: {aum_g:.1f}%")
    else:
        reasons.append("AUM growth data not available")

    if rev_g is not None:
        if rev_g >= 20:   score += 50; reasons.append(f"Revenue growing fast: {rev_g:.1f}%")
        elif rev_g >= 10: score += 35; reasons.append(f"Revenue growing: {rev_g:.1f}%")
        elif rev_g >= 0:  score += 18; reasons.append(f"Revenue flat: {rev_g:.1f}%")
        else:             score += 0;  reasons.append(f"Revenue declining: {rev_g:.1f}%")
    else:
        reasons.append("Revenue growth data not available")

    return PillarResult("Growth", min(score, 100), weight=0.10, reasons=reasons)


# ─────────────────────────────────────────────────────────────────────────────
# Pillar 6 – Governance & Qualitative
# ─────────────────────────────────────────────────────────────────────────────

def _score_governance(d: dict) -> PillarResult:
    score = 100     # start full, deduct for red flags
    reasons = []

    rating = str(d.get("external_rating", "") or "").upper().strip()
    if rating.startswith("AAA"):  score = min(score, 100); reasons.append("External rating AAA")
    elif rating.startswith("AA"): score = min(score, 90);  reasons.append("External rating AA")
    elif rating.startswith("A"):  score = min(score, 75);  reasons.append("External rating A")
    elif rating.startswith("BB"): score = min(score, 55);  reasons.append("External rating BB – sub-investment grade")
    elif rating.startswith("B"):  score = min(score, 40);  reasons.append("External rating B – speculative")
    elif rating.startswith("D"):  score = 0;               reasons.append("Rating D – default/near default")
    elif rating:
        reasons.append(f"Rating: {rating}")

    if d.get("auditor_change_flag") == 1:
        score -= 15; reasons.append("⚠ Auditor change detected")
    if d.get("management_change_flag") == 1:
        score -= 10; reasons.append("⚠ Key management change")
    if d.get("regulatory_issue_flag") == 1:
        score -= 20; reasons.append("🚨 Regulatory action/issue on record")
    if d.get("related_party_flag") == 1:
        score -= 10; reasons.append("⚠ Significant related-party transactions")

    pledge = d.get("promoter_pledge_pct")
    if pledge is not None:
        if pledge > 70:   score -= 15; reasons.append(f"🚨 High promoter pledge: {pledge:.0f}%")
        elif pledge > 40: score -= 8;  reasons.append(f"⚠ Moderate promoter pledge: {pledge:.0f}%")
        else:             reasons.append(f"Promoter pledge low: {pledge:.0f}%")

    return PillarResult("Governance & Rating", max(score, 0), weight=0.10, reasons=reasons)


# ─────────────────────────────────────────────────────────────────────────────
# Red Flag Detection
# ─────────────────────────────────────────────────────────────────────────────

def detect_red_flags(d: dict) -> list[str]:
    flags = []

    if (d.get("gnpa_pct") or 0) > 8:
        flags.append("🚨 GNPA above 8% – severe asset quality stress")
    if (d.get("nnpa_pct") or 0) > 4:
        flags.append("🚨 NNPA above 4% – high net credit losses")
    if (d.get("car") or 99) < 12:
        flags.append("🚨 CAR below 12% – capital adequacy concern")
    if (d.get("interest_coverage") or 99) < 1.2:
        flags.append("🚨 Interest coverage below 1.2x – debt servicing risk")
    if (d.get("liquidity_ratio") or 99) < 1.0:
        flags.append("🚨 Current ratio below 1 – liquidity crunch")
    if (d.get("debt_equity") or 0) > 8:
        flags.append("🚨 D/E above 8x – extremely leveraged")
    if (d.get("collection_efficiency") or 100) < 90:
        flags.append("🚨 Collection efficiency below 90% – repayment stress")
    if d.get("regulatory_issue_flag") == 1:
        flags.append("🚨 Regulatory action on record")
    if (d.get("pcr") or 100) < 35:
        flags.append("⚠ PCR below 35% – under-provisioned")
    if (d.get("roa") or 99) < 0:
        flags.append("🚨 Negative ROA – company in losses")
    if str(d.get("external_rating", "")).upper().startswith("D"):
        flags.append("🚨 Rated D – default or near-default")

    return flags



# ─────────────────────────────────────────────────────────────────────────────
# Rapid AUM Growth vs Asset Quality Deterioration
# ─────────────────────────────────────────────────────────────────────────────

def detect_growth_risk(d: dict) -> list[str]:
    warnings = []

    aum_growth = d.get("aum_growth_yoy")
    gnpa = d.get("gnpa_pct")
    ce = d.get("collection_efficiency")
    car = d.get("car")

    if aum_growth is not None and gnpa is not None:
        if aum_growth > 25 and gnpa > 4:
            warnings.append(
                "⚠ Rapid AUM growth accompanied by elevated GNPA — possible aggressive underwriting"
            )

    if aum_growth is not None and ce is not None:
        if aum_growth > 25 and ce < 92:
            warnings.append(
                "⚠ Fast portfolio growth with declining collection efficiency"
            )

    if aum_growth is not None and car is not None:
        if aum_growth > 25 and car < 15:
            warnings.append(
                "⚠ AUM expanding faster than capital base"
            )

    return warnings


# ─────────────────────────────────────────────────────────────────────────────
# Analyst Summary Generator
# ─────────────────────────────────────────────────────────────────────────────

def _build_summary(company: str, score: float, category: str, pillars: list[PillarResult], flags: list[str]) -> str:
    pillar_lines = "\n".join(
        f"  • {p.name}: {p.score:.0f}/100" for p in pillars
    )
    flag_lines = "\n".join(f"  {f}" for f in flags) if flags else "  None identified."

    return (
        f"{company} has been assessed with a credit score of {score:.1f}/100, "
        f"placing it in the '{category}' risk category.\n\n"
        f"Pillar Scores:\n{pillar_lines}\n\n"
        f"Key Red Flags:\n{flag_lines}\n\n"
        f"Recommendation: {'Proceed with caution and enhanced monitoring.' if category in ('High Risk','Critical Risk') else 'Standard monitoring applies.'}"
    )


# ─────────────────────────────────────────────────────────────────────────────
# Master Scoring Function
# ─────────────────────────────────────────────────────────────────────────────

def score_nbfc(data: dict, company_name: str = "NBFC", quarter: str = "") -> ScoreResult:
    """
    Run the full credit scorecard for one NBFC observation.

    Parameters
    ----------
    data         : Enriched financial data dict (after ratios.calculate_ratios).
    company_name : Display name.
    quarter      : e.g. "Q3 FY25".

    Returns
    -------
    ScoreResult with total_score, risk_category, pillar breakdown, red_flags,
    and analyst_summary.
    """
    d = {k: (_to_float_or_str(v)) for k, v in data.items()}

    pillars = [
        _score_profitability(d),
        _score_asset_quality(d),
        _score_leverage(d),
        _score_liquidity(d),
        _score_growth(d),
        _score_governance(d),
    ]

    total = sum(p.score * p.weight for p in pillars)

    # Ensure score remains between 0 and 100
    total = max(0, min(100, total))

    if total >= 75:
        category, color = "Low Risk",      "green"
    elif total >= 55:
        category, color = "Moderate Risk", "yellow"
    elif total >= 35:
        category, color = "High Risk",     "orange"
    else:
        category, color = "Critical Risk", "red"

    red_flags = detect_red_flags(d)

    # Add growth-risk warnings
    growth_warnings = detect_growth_risk(d)
    red_flags.extend(growth_warnings)

    summary   = _build_summary(company_name, total, category, pillars, red_flags)

    return ScoreResult(
        company_name   = company_name,
        quarter        = quarter,
        total_score    = round(total, 1),
        risk_category  = category,
        risk_color     = color,
        pillars        = pillars,
        red_flags      = red_flags,
        analyst_summary= summary,
    )


def _to_float_or_str(v):
    """Convert to float if numeric; else return string as-is."""
    if v is None:
        return None
    try:
        return float(v)
    except (ValueError, TypeError):
        return str(v)
