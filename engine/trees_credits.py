"""TREES 3.0 credit calculation in Monitoring Report order, plus a benefit-sharing plan (Module 3, ART mode)."""

from __future__ import annotations

from . import rules


def compute_trees_credits(
    emission_reductions: float,
    leakage_pct: float,
    uncertainty_pct: float,
    buffer_pct: float,
    other_programs_tco2e: float = 0,
    no_rights_tco2e: float = 0,
) -> dict:
    order = rules.load("trees_3_0_credit_order")
    labels = {s["key"]: s["label"] for s in order["steps"]}
    er = emission_reductions
    leakage = er * leakage_pct / 100
    uncertainty = er * uncertainty_pct / 100  # TREES 3.0 Eq. 26-30: leakage and uncertainty both apply to gross ERs
    other, no_rights = float(other_programs_tco2e), float(no_rights_tco2e)
    adjusted = max(er - leakage - uncertainty - other - no_rights, 0)
    buffer = adjusted * buffer_pct / 100
    credits = adjusted - buffer
    values = {
        "emission_reductions": er,
        "leakage": -leakage,
        "uncertainty": -uncertainty,
        "other_programs": -other,
        "no_rights": -no_rights,
        "adjusted": adjusted,
        "buffer": -buffer,
        "credits": credits,
    }
    steps = [{"step": n, "key": k, "label": labels[k], "tco2e": values[k]} for n, k in enumerate(values, start=1)]
    return {
        "steps": steps,
        "buffer_tco2e": buffer,
        "net_credits_tco2e": credits,
        "issued_to": order["issued_to"],
        "source": {"source": order["source"], "version": order["version"]},
    }


def benefit_sharing(credits: float, communities_pct: float, nested_pct: float, reserve_pct: float) -> dict:
    shares = {"communities": communities_pct, "nested_projects": nested_pct, "performance_reserve": reserve_pct}
    total = sum(shares.values())
    if any(v < 0 for v in shares.values()) or total > 100:
        raise ValueError(f"benefit shares must be non-negative and add up to at most 100%, got {total:g}%")
    shares["government"] = 100 - total
    return {
        "shares_pct": shares,
        "credits": {k: credits * v / 100 for k, v in shares.items()},
        "note": "ART issues credits only to the Participant (the government); sharing happens after issuance.",
    }
