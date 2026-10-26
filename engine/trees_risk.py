"""TREES Reversal Risk Rating Tool v1.0 (Module 2, ART mode). Numbers come from rules/trees_3_0_rrrt.json."""

from __future__ import annotations

from . import rules

DEFAULTS = {
    "program_governance": "Low",
    "country_governance": "Medium",
    "experience": "Medium",
    "inclusivity": "Low",
    "disturbance": "Medium",
    "mitigation": "Low",
    "reversal_in_past_5_years": False,
}


def score_trees_risk(inputs: dict | None = None) -> dict:
    r = rules.load("trees_3_0_rrrt")
    i = {**DEFAULTS, **(inputs or {})}
    factors = {}
    for key, spec in r["factors"].items():
        level = i[key]
        if level not in spec["levels"]:
            raise ValueError(f"{key} must be one of {list(spec['levels'])}, got {level!r}")
        factors[key] = {"label": spec["label"], "level": level, "pct": spec["levels"][level]}
    if i["reversal_in_past_5_years"]:
        buffer_pct = r["reversal_in_past_5_years_pct"]
        basis = f"reversal reported in the past 5 years -> fixed {buffer_pct}%"
    else:
        raw = r["assumed_risk_pct"] + sum(f["pct"] for f in factors.values())
        buffer_pct = min(raw, r["cap_pct"])
        basis = f"{r['assumed_risk_pct']}% assumed + {raw - r['assumed_risk_pct']}% from factors = {raw}% (cap {r['cap_pct']}%)"
    return {
        "standard": "ART",
        "tool": f"{r['title']} {r['version']}",
        "factors": factors,
        "assumed_pct": r["assumed_risk_pct"],
        "buffer_pct": buffer_pct,
        "basis": basis,
        "placeholder": r["placeholder"],
        "eligible": True,
        "source": {"source": r["source"], "version": r["version"]},
    }
