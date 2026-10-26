"""Baseline and crediting math shared by both standards (Module 1)."""

from __future__ import annotations

from dataclasses import dataclass

LIMITS = {
    "deforestation_ha": (1_000, 50_000),
    "emission_factor": (100, 900),
    "reduction_pct": (0, 80),
    "leakage_pct": (0, 20),
    "uncertainty_pct": (0, 15),
}

DEFAULTS = {
    "deforestation_ha": 20_000,
    "emission_factor": 450,
    "reduction_pct": 30,
    "leakage_pct": 5,
    "uncertainty_pct": 4,
}


@dataclass(frozen=True)
class SimInputs:
    deforestation_ha: float = DEFAULTS["deforestation_ha"]
    emission_factor: float = DEFAULTS["emission_factor"]
    reduction_pct: float = DEFAULTS["reduction_pct"]
    leakage_pct: float = DEFAULTS["leakage_pct"]
    uncertainty_pct: float = DEFAULTS["uncertainty_pct"]

    @classmethod
    def from_dict(cls, d: dict | None) -> "SimInputs":
        d = {**DEFAULTS, **(d or {})}
        values = {}
        for key, (lo, hi) in LIMITS.items():
            v = float(d[key])
            if not lo <= v <= hi:
                raise ValueError(f"{key} must be between {lo} and {hi}, got {v}")
            values[key] = v
        return cls(**values)


def run_simulator(inputs: SimInputs) -> dict:
    """Baseline -> gross reductions -> after leakage -> after uncertainty (all tCO2e/yr)."""
    baseline = inputs.deforestation_ha * inputs.emission_factor
    gross = baseline * inputs.reduction_pct / 100
    leakage = gross * inputs.leakage_pct / 100
    after_leakage = gross - leakage
    uncertainty = after_leakage * inputs.uncertainty_pct / 100
    after_uncertainty = after_leakage - uncertainty
    return {
        "baseline_tco2e": baseline,
        "gross_reductions_tco2e": gross,
        "leakage_deduction_tco2e": leakage,
        "after_leakage_tco2e": after_leakage,
        "uncertainty_deduction_tco2e": uncertainty,
        "after_uncertainty_tco2e": after_uncertainty,
    }


def apply_jnr_buffer(after_uncertainty: float, buffer_pct: float, guarantee_pct: float, eligible: bool) -> dict:
    """JNR: the buffer applies only to the share of net benefit not covered by a replacement guarantee."""
    if not eligible:
        return {"buffer_tco2e": 0.0, "net_credits_tco2e": 0.0, "eligible": False}
    buffered_share = 1 - guarantee_pct / 100
    buffer = after_uncertainty * buffered_share * buffer_pct / 100
    return {"buffer_tco2e": buffer, "net_credits_tco2e": after_uncertainty - buffer, "eligible": True}
