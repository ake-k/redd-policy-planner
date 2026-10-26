"""Engine math against hand-calculated cases."""

import pytest

from engine import calculate, compare_standards
from engine.jnr_allocation import allocate_jnr
from engine.jnr_risk import score_jnr_risk
from engine.simulator import SimInputs, run_simulator
from engine.trees_credits import benefit_sharing, compute_trees_credits
from engine.trees_risk import score_trees_risk


def test_simulator_defaults_by_hand():
    out = run_simulator(SimInputs())
    # 20,000 ha x 450 = 9,000,000; x30% = 2,700,000; -5% = 2,565,000; -4% = 2,462,400
    assert out["baseline_tco2e"] == 9_000_000
    assert out["gross_reductions_tco2e"] == 2_700_000
    assert out["after_leakage_tco2e"] == pytest.approx(2_565_000)
    assert out["after_uncertainty_tco2e"] == pytest.approx(2_462_400)


def test_simulator_rejects_out_of_range():
    with pytest.raises(ValueError):
        SimInputs.from_dict({"reduction_pct": 95})


def test_jnr_default_rating_by_hand():
    r = score_jnr_risk()
    # PG: WGI -0.3 -> 2, readiness -2 -> 0
    # PDS: 10 -3 (commodity) -2 (green economy) -1 (readiness funding) = 4
    # CR: law not enacted 4, +1 tenure disputes, -1 statutory rights, revenue 25% -> +2 = 6
    # FR: 6 -1 (domestic market) = 5
    # PL: 25 - 60/5 = 13
    # NR: minor, every 10-25 years = 5
    assert r["categories"] == {"PG": 0, "PDS": 4, "CR": 6, "FR": 5, "PL": 13, "NR": 5}
    assert r["rating"] == 33 and r["buffer_pct"] == 33 and r["eligible"]


def test_jnr_longevity_under_40_fails():
    r = score_jnr_risk({"longevity_years": 30})
    assert not r["eligible"] and r["buffer_pct"] is None
    out = calculate({"standard": "JNR", "jnr_risk": {"longevity_years": 30}})
    assert out["credits"]["net_credits_tco2e"] == 0


def test_jnr_rating_floor_of_10():
    best = {
        "wgi_avg": 1.0, "protected_from_government_change": True, "governance_readiness_underway": True,
        "commodity_production_maintained": True, "subsistence_drivers_addressed": True, "green_economy_plan": True,
        "strategy_with_deforestation_agents": True, "readiness_funding_received": True,
        "carbon_rights_law": True, "tenure_disputes_over_10pct": False, "statutory_land_rights": True,
        "dispute_mechanism": True, "non_redd_revenue_pct": 10, "stakeholder_revenue_policy": True,
        "breakeven_or_commercial_revenue": True, "funding_secured_40pct": True, "domestic_carbon_market": True,
        "public_private_partnerships": True, "legal_agreement_100yr": True, "nr_significance": "insignificant",
    }
    r = score_jnr_risk(best)
    assert r["raw_sum"] == 0
    assert r["rating"] == 10 and r["minimum_applied"]


def test_jnr_100yr_agreement_and_rounding_up():
    r = score_jnr_risk({"legal_agreement_100yr": True, "nr_mitigation": True})
    # PL -> 0; NR 5 x 0.8 = 4; total 0+4+6+5+0+4 = 19
    assert r["categories"]["PL"] == 0 and r["categories"]["NR"] == pytest.approx(4)
    assert r["rating"] == 19
    r2 = score_jnr_risk({"longevity_years": 50, "legal_requirement_to_continue": True})
    # PL 25 - 50/4 = 12.5 -> total 0+4+6+5+12.5+5 = 32.5 -> rounds up to 33
    assert r2["rating"] == 33


def test_jnr_natural_risk_fail_and_rating_above_60_fail():
    assert not score_jnr_risk({"nr_significance": "catastrophic", "nr_likelihood": "1-10"})["eligible"]
    worst = {"wgi_avg": -1.5, "subnational_no_national_support": True, "governance_readiness_underway": False,
             "commodity_production_maintained": False, "green_economy_plan": False, "readiness_funding_received": False,
             "statutory_land_rights": False, "non_redd_revenue_pct": 50, "domestic_carbon_market": False,
             "longevity_years": 40, "nr_significance": "devastating", "nr_likelihood": "1-10"}
    r = score_jnr_risk(worst)
    # PG 10, PDS 10, CR 9, FR 6, PL 25-8=17, NR 30 -> 82
    assert r["rating"] == 82 and not r["eligible"]


def test_jnr_guarantee_reduces_buffer():
    full = calculate({"standard": "JNR"})
    half = calculate({"standard": "JNR", "jnr_risk": {"guarantee_pct": 50}})
    assert full["credits"]["buffer_tco2e"] == pytest.approx(2_462_400 * 0.33)
    assert half["credits"]["buffer_tco2e"] == pytest.approx(2_462_400 * 0.5 * 0.33)


def test_trees_risk_defaults_cap_and_reversal():
    # 5 assumed + Low 0 + Medium 1 + Medium 1 + Low 0 + Medium 5 + Low 0 = 12
    assert score_trees_risk()["buffer_pct"] == 12
    worst = {k: "High" for k in ("program_governance", "country_governance", "experience", "inclusivity", "disturbance", "mitigation")}
    assert score_trees_risk(worst)["buffer_pct"] == 25  # 5+2+3+3+2+8+2 = 25, at the cap
    assert score_trees_risk({"reversal_in_past_5_years": True})["buffer_pct"] == 30


def test_trees_credit_order_by_hand():
    tc = compute_trees_credits(1_000_000, 5, 4, 12, other_programs_tco2e=10_000, no_rights_tco2e=2_000)
    v = {s["key"]: s["tco2e"] for s in tc["steps"]}
    assert [s["step"] for s in tc["steps"]] == list(range(1, 9))
    assert v["leakage"] == -50_000
    assert v["uncertainty"] == pytest.approx(-40_000)  # 4% of gross, not of the post-leakage balance
    assert v["adjusted"] == pytest.approx(898_000)
    assert v["buffer"] == pytest.approx(-107_760)
    assert v["credits"] == pytest.approx(790_240)


def test_benefit_sharing_sums_to_100():
    b = benefit_sharing(1000, 30, 15, 10)
    assert b["shares_pct"]["government"] == 45
    assert sum(b["credits"].values()) == pytest.approx(1000)
    with pytest.raises(ValueError):
        benefit_sharing(1000, 60, 30, 20)


def test_allocation_by_hand():
    a = allocate_jnr(20_000, 450, [{"name": "A", "share_pct": 10, "emission_factor": 500}])
    assert a["rows"][0]["hectares"] == 2_000 and a["rows"][0]["baseline_tco2e"] == 1_000_000
    assert a["rows"][-1]["hectares"] == 18_000
    with pytest.raises(ValueError):
        allocate_jnr(20_000, 450, [{"name": "A", "share_pct": 70, "emission_factor": 1}, {"name": "B", "share_pct": 40, "emission_factor": 1}])


def test_compare_standards_defaults():
    c = compare_standards()
    assert c["JNR"]["net_credits_tco2e"] == pytest.approx(2_462_400 * 0.67)
    assert c["ART"]["net_credits_tco2e"] == pytest.approx(2_700_000 * 0.91 * 0.88)  # 2,162,160
    assert c["difference_jnr_minus_art_tco2e"] == pytest.approx(2_462_400 * 0.67 - 2_162_160)
