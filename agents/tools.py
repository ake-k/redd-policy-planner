"""Tool schemas and implementations. Every calculator tool is a thin wrapper around engine/ and returns JSON."""

from __future__ import annotations

import engine
from engine import jnr_risk, rules, trees_risk

from . import library, safety
from .llm import RunContext

PATCH_HELP = (
    "Optional partial dashboard state, merged onto the user's current dashboard state. Keys: "
    "sim{deforestation_ha 1000-50000, emission_factor 100-900, reduction_pct 0-80, leakage_pct 0-20, uncertainty_pct 0-15}; "
    f"jnr_risk{{{', '.join(jnr_risk.DEFAULTS)}}} (nr_significance: catastrophic|devastating|massive|major|minor|insignificant; "
    "nr_likelihood: 1-10|10-25|25-50|50-100|100+; booleans for yes/no items; guarantee_pct 0-100); "
    f"trees_risk{{{', '.join(trees_risk.DEFAULTS)}}} (levels High|Medium|Low; program_governance, inclusivity and mitigation "
    "only High|Low; reversal_in_past_5_years boolean); allocation{projects:[{name, share_pct, emission_factor}]} (max 5); "
    "trees_credits{other_programs_tco2e, no_rights_tco2e}; benefit{communities_pct, nested_pct, reserve_pct}."
)


def _patch_param() -> dict:
    return {"type": "object", "description": PATCH_HELP}


def _fn(name: str, description: str, properties: dict, required: list[str] | None = None) -> dict:
    return {"type": "function", "name": name, "description": description, "strict": False,
            "parameters": {"type": "object", "properties": properties, "required": required or []}}


def _round(x):
    if isinstance(x, float):
        return round(x) if abs(x) >= 100 else round(x, 2)
    if isinstance(x, dict):
        return {k: _round(v) for k, v in x.items()}
    if isinstance(x, list):
        return [_round(v) for v in x]
    return x


def _state(ctx: RunContext, patch: dict | None) -> dict:
    return engine.merge_state(ctx.dashboard_state, patch or {})


# ---------------------------------------------------------------- Scenario Analyst tools

def run_simulator(ctx: RunContext, patch: dict | None = None, standard: str | None = None) -> dict:
    out = engine.calculate(_state(ctx, patch), standard)
    return _round({"standard": out["standard"], "simulator": out["simulator"], "buffer_pct": out["risk"]["buffer_pct"],
                   "eligible": out["credits"]["eligible"], "buffer_withheld_tco2e": out["credits"]["buffer_tco2e"],
                   "net_credits_tco2e": out["credits"]["net_credits_tco2e"]})


def score_jnr_risk(ctx: RunContext, patch: dict | None = None) -> dict:
    r = jnr_risk.score_jnr_risk(_state(ctx, patch)["jnr_risk"])
    return _round({k: r[k] for k in ("tool", "categories", "detail", "raw_sum", "rating", "minimum_applied", "eligible", "fails", "buffer_pct", "guarantee_pct")})


def score_trees_risk(ctx: RunContext, patch: dict | None = None) -> dict:
    r = trees_risk.score_trees_risk(_state(ctx, patch)["trees_risk"])
    return _round({k: r[k] for k in ("tool", "factors", "assumed_pct", "buffer_pct", "basis")})


def allocate_jnr(ctx: RunContext, patch: dict | None = None) -> dict:
    return _round(engine.calculate(_state(ctx, patch), "JNR")["module3"]["allocation"])


def compute_trees_credits(ctx: RunContext, patch: dict | None = None) -> dict:
    m3 = engine.calculate(_state(ctx, patch), "ART")["module3"]
    return _round({"steps": m3["trees_credits"]["steps"], "issued_to": m3["trees_credits"]["issued_to"],
                   "benefit_sharing": m3["benefit"]})


def compare_standards(ctx: RunContext, patch: dict | None = None) -> dict:
    return _round(engine.compare_standards(_state(ctx, patch)))


def set_dashboard_state(ctx: RunContext, patch: dict, standard: str | None = None) -> dict:
    """Only proposes new on-screen inputs. The user sees them applied with an Undo button; nothing else changes."""
    new = _state(ctx, patch)
    if standard:
        new["standard"] = standard
    engine.calculate(new)  # validates every input; raises on out-of-range values
    ctx.proposed_state = new
    return {"ok": True, "applied": "on-screen inputs only (the user can undo)"}


# ---------------------------------------------------------------- Rules Navigator tools

def search_library(ctx: RunContext, query: str, standard: str = "any") -> dict:
    found = library.search_library(query, standard, session_id=ctx.session_id, run_id=ctx.run_id)
    ctx.retrieved += [{k: c[k] for k in ("id", "source", "version", "section", "page")} for c in found["results"]]
    chunks = [{"id": c["id"], "source": c["source"], "version": c["version"], "section": c["section"], "page": c["page"],
               "text": safety.untrusted(c["id"], c["text"])} for c in found["results"]]
    out: dict = {"results": chunks}
    if found["blocked"]:
        out["note"] = f"{len(found['blocked'])} chunk(s) were withheld by the injection screen."
    return out


def get_rule(ctx: RunContext, rule_id: str) -> dict:
    r = rules.load(rule_id)
    ctx.retrieved.append({"id": rule_id, "source": r["source"], "version": r["version"], "section": r.get("section", ""), "page": ""})
    return r


def get_sources(ctx: RunContext, standard: str = "any") -> dict:
    s = rules.load("sources")
    return s if standard == "any" else {standard: s[standard]}


SCENARIO_TOOLS = [
    _fn("run_simulator", "Baseline -> gross reductions -> leakage -> uncertainty -> buffer -> net credits for one standard.",
        {"patch": _patch_param(), "standard": {"type": "string", "enum": ["JNR", "ART"]}}),
    _fn("score_jnr_risk", "JNR Non-Permanence Risk Tool v4.1 rating, category scores and buffer %.", {"patch": _patch_param()}),
    _fn("score_trees_risk", "TREES Reversal Risk Rating Tool buffer %, by factor.", {"patch": _patch_param()}),
    _fn("allocate_jnr", "JNR Scenario 1 VT0007-style allocation of baseline hectares and tCO2e to nested projects.", {"patch": _patch_param()}),
    _fn("compute_trees_credits", "TREES 3.0 credit calculation in Monitoring Report order, plus the benefit-sharing split.", {"patch": _patch_param()}),
    _fn("compare_standards", "Runs the same inputs through JNR and ART; returns buffer %, buffer, net credits and the difference.", {"patch": _patch_param()}),
    _fn("set_dashboard_state", "Moves the on-screen inputs to the scenario you ran, so the user sees it. Call once, last.",
        {"patch": _patch_param(), "standard": {"type": "string", "enum": ["JNR", "ART"]}}, ["patch"]),
]
SCENARIO_IMPLS = {"run_simulator": run_simulator, "score_jnr_risk": score_jnr_risk, "score_trees_risk": score_trees_risk,
                  "allocate_jnr": allocate_jnr, "compute_trees_credits": compute_trees_credits,
                  "compare_standards": compare_standards, "set_dashboard_state": set_dashboard_state}

RULES_TOOLS = [
    _fn("search_library", "Keyword search over official rule excerpts. Returns up to 5 chunks with source, version, section, page.",
        {"query": {"type": "string"}, "standard": {"type": "string", "enum": ["JNR", "ART", "any"]}}, ["query"]),
    _fn("get_rule", "Exact machine-readable rule entry with its source.",
        {"rule_id": {"type": "string", "enum": ["jnr_nprt_v4_1", "trees_3_0_rrrt", "trees_3_0_credit_order"]}}, ["rule_id"]),
    _fn("get_sources", "Official document titles, versions and URLs for a standard.",
        {"standard": {"type": "string", "enum": ["JNR", "ART", "any"]}}),
]
RULES_IMPLS = {"search_library": search_library, "get_rule": get_rule, "get_sources": get_sources}
