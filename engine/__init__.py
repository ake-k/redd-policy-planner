"""Deterministic calculation engine. Every number the app or the agents show comes from here, never from a model."""

from __future__ import annotations

import copy

from . import jnr_risk, simulator, trees_risk
from .jnr_allocation import DEFAULT_PROJECTS, allocate_jnr
from .simulator import SimInputs, apply_jnr_buffer, run_simulator
from .trees_credits import benefit_sharing, compute_trees_credits

STANDARDS = ("JNR", "ART")

DEFAULT_STATE = {
    "jurisdiction": "Sample Province",
    "standard": "JNR",
    "sim": dict(simulator.DEFAULTS),
    "jnr_risk": dict(jnr_risk.DEFAULTS),
    "trees_risk": dict(trees_risk.DEFAULTS),
    "allocation": {"projects": copy.deepcopy(DEFAULT_PROJECTS)},
    "trees_credits": {"other_programs_tco2e": 0, "no_rights_tco2e": 0},
    "benefit": {"communities_pct": 30, "nested_pct": 15, "reserve_pct": 10},
}


def merge_state(base: dict, patch: dict | None) -> dict:
    """Deep-merge a partial state onto a full one (lists are replaced, not merged)."""
    out = copy.deepcopy(base)
    for k, v in (patch or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = merge_state(out[k], v)
        else:
            out[k] = copy.deepcopy(v)
    return out


def calculate(state: dict | None = None, standard: str | None = None) -> dict:
    """Run all three modules for one standard and return everything the dashboard draws."""
    s = merge_state(DEFAULT_STATE, state)
    std = standard or s["standard"]
    if std not in STANDARDS:
        raise ValueError(f"standard must be JNR or ART, got {std!r}")
    inputs = SimInputs.from_dict(s["sim"])
    sim = run_simulator(inputs)

    if std == "JNR":
        risk = jnr_risk.score_jnr_risk(s["jnr_risk"])
        credit = apply_jnr_buffer(sim["after_uncertainty_tco2e"], risk["buffer_pct"] or 0, risk["guarantee_pct"], risk["eligible"])
        module3 = {"allocation": allocate_jnr(inputs.deforestation_ha, inputs.emission_factor, s["allocation"]["projects"])}
    else:
        risk = trees_risk.score_trees_risk(s["trees_risk"])
        tc = compute_trees_credits(
            sim["gross_reductions_tco2e"], inputs.leakage_pct, inputs.uncertainty_pct, risk["buffer_pct"],
            s["trees_credits"]["other_programs_tco2e"], s["trees_credits"]["no_rights_tco2e"],
        )
        credit = {"buffer_tco2e": tc["buffer_tco2e"], "net_credits_tco2e": tc["net_credits_tco2e"], "eligible": True}
        b = s["benefit"]
        module3 = {"trees_credits": tc, "benefit": benefit_sharing(tc["net_credits_tco2e"], b["communities_pct"], b["nested_pct"], b["reserve_pct"])}

    return {
        "standard": std,
        "jurisdiction": s["jurisdiction"],
        "simulator": sim,
        "risk": risk,
        "credits": credit,
        "module3": module3,
        "state": {**s, "standard": std},
    }


def compare_standards(state: dict | None = None) -> dict:
    jnr, art = calculate(state, "JNR"), calculate(state, "ART")
    j, a = jnr["credits"]["net_credits_tco2e"], art["credits"]["net_credits_tco2e"]
    return {
        "JNR": {"buffer_pct": jnr["risk"]["buffer_pct"], "eligible": jnr["credits"]["eligible"],
                "buffer_tco2e": jnr["credits"]["buffer_tco2e"], "net_credits_tco2e": j},
        "ART": {"buffer_pct": art["risk"]["buffer_pct"], "buffer_tco2e": art["credits"]["buffer_tco2e"], "net_credits_tco2e": a},
        "difference_jnr_minus_art_tco2e": j - a,
    }
