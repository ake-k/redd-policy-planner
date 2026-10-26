"""JNR Non-Permanence Risk Tool v4.1 scoring (Module 2, JNR mode). Numbers come from rules/jnr_nprt_v4_1.json."""

from __future__ import annotations

import math

from . import rules

DEFAULTS = {
    "wgi_avg": -0.3,
    "subnational_no_national_support": False,
    "protected_from_government_change": False,
    "governance_readiness_underway": True,
    "commodity_production_maintained": True,
    "subsistence_drivers_addressed": False,
    "green_economy_plan": True,
    "strategy_with_deforestation_agents": False,
    "readiness_funding_received": True,
    "carbon_rights_law": False,
    "tenure_disputes_over_10pct": True,
    "statutory_land_rights": True,
    "dispute_mechanism": False,
    "non_redd_revenue_pct": 25,
    "stakeholder_revenue_policy": False,
    "breakeven_or_commercial_revenue": False,
    "funding_secured_40pct": False,
    "domestic_carbon_market": True,
    "public_private_partnerships": False,
    "legal_agreement_100yr": False,
    "longevity_years": 60,
    "legal_requirement_to_continue": False,
    "has_longevity_plan": True,
    "nr_significance": "minor",
    "nr_likelihood": "10-25",
    "nr_mitigation": False,
    "guarantee_pct": 0,
}


def _ceil(x: float) -> int:
    return math.ceil(round(x, 9))


def score_jnr_risk(inputs: dict | None = None) -> dict:
    r = rules.load("jnr_nprt_v4_1")
    i = {**DEFAULTS, **(inputs or {})}
    fails: list[str] = []
    detail: dict[str, list[str]] = {}

    # Political and governance
    pg_rules = r["political_governance"]
    wgi = float(i["wgi_avg"])
    pg = next(b["score"] for b in pg_rules["wgi_bands"] if b["below"] is None or wgi < b["below"])
    detail["PG"] = [f"WGI average {wgi:+.2f} -> base {pg}"]
    for key, pts in pg_rules["adjustments"].items():
        if i[key]:
            pg += pts
            detail["PG"].append(f"{key} {pts:+d}")
    pg = max(pg, 0)

    # Program design and strategy
    pds_rules = r["program_design"]
    pds = pds_rules["default"]
    detail["PDS"] = [f"default {pds}"]
    for key, pts in pds_rules["mitigations"].items():
        if i[key]:
            pds += pts
            detail["PDS"].append(f"{key} {pts:+d}")
    pds = max(pds, 0)

    # Carbon rights and revenues
    cr_rules = r["carbon_rights"]
    cr = cr_rules["law_enacted"] if i["carbon_rights_law"] else cr_rules["law_not_enacted"]
    detail["CR"] = [f"carbon rights law {'enacted' if i['carbon_rights_law'] else 'not enacted'} -> {cr}"]
    for key in ("tenure_disputes_over_10pct", "statutory_land_rights", "dispute_mechanism"):
        if i[key]:
            cr += cr_rules[key]
            detail["CR"].append(f"{key} {cr_rules[key]:+d}")
    rev = float(i["non_redd_revenue_pct"])
    rev_score = next(b["score"] for b in cr_rules["non_redd_revenue_bands"] if b["above"] is None or rev > b["above"])
    cr += rev_score
    detail["CR"].append(f"non-REDD+ revenue use {rev:g}% -> +{rev_score}")
    if i["stakeholder_revenue_policy"]:
        cr += cr_rules["stakeholder_revenue_policy"]
        detail["CR"].append(f"stakeholder_revenue_policy {cr_rules['stakeholder_revenue_policy']:+d}")
    cr = max(cr, 0)

    # Funding
    fr_rules = r["funding"]
    fr = fr_rules["default"]
    detail["FR"] = [f"default {fr}"]
    for key, pts in fr_rules["mitigations"].items():
        if i[key]:
            fr += pts
            detail["FR"].append(f"{key} {pts:+d}")
    fr = max(fr, 0)

    # Program longevity
    pl_rules = r["program_longevity"]
    years = float(i["longevity_years"])
    pl: float | str
    if i["legal_agreement_100yr"]:
        pl = 0
        detail["PL"] = [f"legally binding {pl_rules['legal_agreement_years']}-year agreement -> 0"]
    elif years < pl_rules["minimum_years"] or not i["has_longevity_plan"]:
        pl = "FAIL"
        reason = f"longevity {years:g} < {pl_rules['minimum_years']} years" if years < pl_rules["minimum_years"] else "no management, financial and monitoring plan"
        detail["PL"] = [f"FAIL: {reason}"]
        fails.append(f"Program longevity: {reason}")
    else:
        div = pl_rules["divisor_with_legal_requirement"] if i["legal_requirement_to_continue"] else pl_rules["divisor_without_legal_requirement"]
        pl = max(pl_rules["base"] - years / div, 0)
        detail["PL"] = [f"{pl_rules['base']} - {years:g}/{div} = {pl:g}"]

    # Natural risk
    nr_rules = r["natural_risk"]
    sig, lik = i["nr_significance"], i["nr_likelihood"]
    if sig not in nr_rules["matrix"] or lik not in nr_rules["likelihood_levels"]:
        raise ValueError(f"unknown natural risk level: {sig} / {lik}")
    nr: float | str = nr_rules["matrix"][sig][nr_rules["likelihood_levels"].index(lik)]
    detail["NR"] = [f"{sig} significance, every {lik} years -> {nr}"]
    if nr == "FAIL":
        fails.append("Natural risk: catastrophic loss expected every 1-10 years")
    elif i["nr_mitigation"]:
        nr = nr * nr_rules["mitigation_multiplier"]
        detail["NR"].append(f"proven mitigation x{nr_rules['mitigation_multiplier']} -> {nr:g}")

    categories = {"PG": pg, "PDS": pds, "CR": cr, "FR": fr, "PL": pl, "NR": nr}
    numeric_sum = sum(v for v in categories.values() if not isinstance(v, str))
    overall = r["overall"]
    rating = max(_ceil(numeric_sum), overall["minimum_rating"])
    if rating > overall["fail_above"]:
        fails.append(f"Overall rating {rating} is above {overall['fail_above']}")
    eligible = not fails
    return {
        "standard": "JNR",
        "tool": f"{r['title']} {r['version']}",
        "categories": categories,
        "detail": detail,
        "raw_sum": numeric_sum,
        "rating": rating,
        "minimum_applied": _ceil(numeric_sum) < overall["minimum_rating"],
        "eligible": eligible,
        "fails": fails,
        "buffer_pct": rating if eligible else None,
        "guarantee_pct": float(i["guarantee_pct"]),
        "source": {"source": r["source"], "version": r["version"]},
    }
