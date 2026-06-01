"""
flags.py
--------
Standalone red-flag checker and governance signal detector.

Also provides a structured output suitable for dashboard display.
"""

from dataclasses import dataclass


@dataclass
class Flag:
    severity: str   # "critical" | "warning" | "info"
    message:  str
    field:    str   # which data field triggered this


SEVERITY_EMOJI = {
    "critical": "🚨",
    "warning":  "⚠️",
    "info":     "ℹ️",
}

SEVERITY_COLOR = {
    "critical": "#FF4B4B",
    "warning":  "#FFA500",
    "info":     "#1E90FF",
}


def get_flags(data: dict) -> list[Flag]:
    """
    Generate a list of Flag objects for a given NBFC data dict.
    Covers asset quality, liquidity, leverage, capital, governance.
    """
    flags: list[Flag] = []

    def _f(v, field):
        return float(v) if v is not None else None

    # ── Asset Quality ────────────────────────────────────────────────────────
    gnpa = _f(data.get("gnpa_pct"), "gnpa_pct")
    nnpa = _f(data.get("nnpa_pct"), "nnpa_pct")
    pcr  = _f(data.get("pcr"), "pcr")
    ce   = _f(data.get("collection_efficiency"), "collection_efficiency")

    if gnpa is not None:
        if gnpa > 8:
            flags.append(Flag("critical", f"GNPA {gnpa:.1f}% exceeds 8% — severe stress", "gnpa_pct"))
        elif gnpa > 5:
            flags.append(Flag("warning",  f"GNPA {gnpa:.1f}% is elevated (>5%)", "gnpa_pct"))
        elif gnpa > 3:
            flags.append(Flag("info",     f"GNPA {gnpa:.1f}% — monitor trend", "gnpa_pct"))

    if nnpa is not None:
        if nnpa > 4:
            flags.append(Flag("critical", f"NNPA {nnpa:.1f}% exceeds 4%", "nnpa_pct"))
        elif nnpa > 2:
            flags.append(Flag("warning",  f"NNPA {nnpa:.1f}% elevated", "nnpa_pct"))

    if pcr is not None and pcr < 35:
        flags.append(Flag("critical", f"PCR {pcr:.0f}% below 35% — under-provisioned", "pcr"))
    elif pcr is not None and pcr < 50:
        flags.append(Flag("warning",  f"PCR {pcr:.0f}% below 50%", "pcr"))

    if ce is not None and ce < 90:
        flags.append(Flag("critical", f"Collection efficiency {ce:.1f}% below 90%", "collection_efficiency"))
    elif ce is not None and ce < 95:
        flags.append(Flag("warning",  f"Collection efficiency {ce:.1f}% declining", "collection_efficiency"))

    # ── Liquidity / Coverage ─────────────────────────────────────────────────
    ic = _f(data.get("interest_coverage"), "interest_coverage")
    cr = _f(data.get("liquidity_ratio"), "liquidity_ratio")

    if ic is not None:
        if ic < 1.0:
            flags.append(Flag("critical", f"Interest coverage {ic:.2f}x — unable to cover interest", "interest_coverage"))
        elif ic < 1.5:
            flags.append(Flag("warning",  f"Interest coverage {ic:.2f}x — thin margin", "interest_coverage"))

    if cr is not None:
        if cr < 1.0:
            flags.append(Flag("critical", f"Current ratio {cr:.2f}x below 1 — liquidity crunch", "liquidity_ratio"))
        elif cr < 1.2:
            flags.append(Flag("warning",  f"Current ratio {cr:.2f}x — tight liquidity", "liquidity_ratio"))

    # ── Leverage & Capital ───────────────────────────────────────────────────
    de  = _f(data.get("debt_equity"), "debt_equity")
    car = _f(data.get("car"), "car")
    roa = _f(data.get("roa"), "roa")

    if de is not None and de > 8:
        flags.append(Flag("critical", f"D/E {de:.1f}x — extremely high leverage", "debt_equity"))
    elif de is not None and de > 6:
        flags.append(Flag("warning",  f"D/E {de:.1f}x — leverage elevated", "debt_equity"))

    if car is not None:
        if car < 12:
            flags.append(Flag("critical", f"CAR {car:.1f}% below 12% RBI minimum", "car"))
        elif car < 15:
            flags.append(Flag("warning",  f"CAR {car:.1f}% near minimum threshold", "car"))

    if roa is not None and roa < 0:
        flags.append(Flag("critical", f"Negative ROA {roa:.2f}% — company reporting losses", "roa"))

    # ── Governance ───────────────────────────────────────────────────────────
    if data.get("regulatory_issue_flag") == 1:
        flags.append(Flag("critical", "Regulatory action / RBI notice on record", "regulatory_issue_flag"))

    if data.get("auditor_change_flag") == 1:
        flags.append(Flag("warning", "Statutory auditor changed this period", "auditor_change_flag"))

    if data.get("management_change_flag") == 1:
        flags.append(Flag("warning", "Key management change detected", "management_change_flag"))

    pledge = _f(data.get("promoter_pledge_pct"), "promoter_pledge_pct")
    if pledge is not None:
        if pledge > 70:
            flags.append(Flag("critical", f"Promoter pledge {pledge:.0f}% — very high risk", "promoter_pledge_pct"))
        elif pledge > 40:
            flags.append(Flag("warning",  f"Promoter pledge {pledge:.0f}%", "promoter_pledge_pct"))

    if data.get("related_party_flag") == 1:
        flags.append(Flag("warning", "Significant related-party transactions", "related_party_flag"))

    # Sort: critical first
    severity_order = {"critical": 0, "warning": 1, "info": 2}
    flags.sort(key=lambda f: severity_order.get(f.severity, 3))

    return flags


def flags_to_text(flags: list[Flag]) -> list[str]:
    """Return a plain list of formatted flag strings for display."""
    return [f"{SEVERITY_EMOJI.get(f.severity, '')} {f.message}" for f in flags]
