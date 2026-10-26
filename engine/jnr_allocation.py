"""VT0007-style allocation of the jurisdictional baseline to nested projects (Module 3, JNR mode)."""

from __future__ import annotations

MAX_PROJECTS = 5

DEFAULT_PROJECTS = [
    {"name": "Project A", "share_pct": 12, "emission_factor": 520},
    {"name": "Project B", "share_pct": 8, "emission_factor": 380},
]


def allocate_jnr(deforestation_ha: float, jurisdiction_ef: float, projects: list[dict] | None = None) -> dict:
    projects = DEFAULT_PROJECTS if projects is None else projects
    if len(projects) > MAX_PROJECTS:
        raise ValueError(f"at most {MAX_PROJECTS} projects")
    total_share = sum(float(p["share_pct"]) for p in projects)
    if total_share > 100:
        raise ValueError(f"project shares add up to {total_share:g}%, more than 100%")
    rows = []
    for p in projects:
        ha = deforestation_ha * float(p["share_pct"]) / 100
        rows.append({
            "name": str(p["name"])[:40],
            "share_pct": float(p["share_pct"]),
            "hectares": ha,
            "emission_factor": float(p["emission_factor"]),
            "baseline_tco2e": ha * float(p["emission_factor"]),
        })
    rest_ha = deforestation_ha * (100 - total_share) / 100
    rows.append({
        "name": "Rest of jurisdiction",
        "share_pct": 100 - total_share,
        "hectares": rest_ha,
        "emission_factor": jurisdiction_ef,
        "baseline_tco2e": rest_ha * jurisdiction_ef,
    })
    return {
        "scenario": "JNR Scenario 1",
        "rows": rows,
        "note": "Share of allocated risk stands in for the risk-map output. In Scenario 1 the government registers "
                "the jurisdictional reference level but receives no credits; projects are credited.",
    }
