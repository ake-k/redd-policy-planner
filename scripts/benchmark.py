"""Runs 10 fixed questions with prompt caching on, then off, and saves tokens, cost and pass/fail to docs/benchmark.csv.

Usage: python scripts/benchmark.py            (about 20 model runs; a few cents)
Pass/fail compares the agents' numbers to the engine's own outputs, computed here without any model.
"""

from __future__ import annotations

import csv
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config  # noqa: E402
import engine  # noqa: E402
from agents import orchestrator, verifier  # noqa: E402

D = engine.DEFAULT_STATE


def net(patch: dict, std: str) -> float:
    return engine.calculate(engine.merge_state(D, patch), std)["credits"]["net_credits_tco2e"]


def jnr_buffer(patch: dict) -> float:
    return engine.calculate(engine.merge_state(D, patch), "JNR")["risk"]["buffer_pct"]


CASES = [
    ("Compare net credits under JNR and ART for the default inputs.", "numbers", [net({}, "JNR"), net({}, "ART")]),
    ("Under JNR, what happens to our buffer if we get a 100-year legal agreement?", "numbers",
     [jnr_buffer({"jnr_risk": {"legal_agreement_100yr": True}})]),
    ("What does TREES 3.0 say about deducting project credits?", "cited", []),
    ("If we pass a carbon rights law and secure 40% of funding, what is our JNR buffer?", "numbers",
     [jnr_buffer({"jnr_risk": {"carbon_rights_law": True, "funding_secured_40pct": True}})]),
    ("What is our ART buffer if a reversal was reported in the past 5 years?", "numbers", [30]),
    ("Under ART, how many net credits do we get if we cut deforestation by 50%?", "numbers",
     [net({"sim": {"reduction_pct": 50}}, "ART")]),
    ("How does the JNR Non-Permanence Risk Tool turn the risk rating into a buffer?", "cited", []),
    ("What does ART say about the 5% assumed reversal risk?", "cited", []),
    ("Are we eligible under JNR if our program longevity is only 30 years?", "text", [("not eligible", "ineligible", "fail")]),
    ("Under JNR Scenario 1, does the government receive credits?", "cited", []),
]


def passed(kind: str, expected: list, r: dict) -> bool:
    p = r["payload"]
    if r["kind"] in ("error", "budget", "blocked"):
        return False
    if kind == "cited":
        return bool(p.get("citations")) and r["verified"] is not False
    text = " ".join([p.get("summary", ""), p.get("answer", "")] + p.get("caveats", []))
    if kind == "text":
        return all(any(alt in text.lower() for alt in e) for e in expected)  # each item: tuple of accepted phrasings
    found = {abs(float(k["value"])) for k in p.get("key_numbers", [])} | {abs(v) for _, v in verifier.numbers_in(text)}
    return all(any(abs(f - e) <= max(abs(e) * 0.006, 0.5) for f in found) for e in expected)


def main() -> None:
    config.ANSWER_CACHE = False  # measure the model, not the answer cache
    out = config.REPO_DIR / "docs" / "benchmark.csv"
    rows = []
    for caching in (True, False):
        config.PROMPT_CACHING = caching
        for i, (q, kind, expected) in enumerate(CASES, 1):
            r = orchestrator.handle(q, D, f"benchmark-{'on' if caching else 'off'}")
            t = r["usage"]["total"]
            ok = passed(kind, expected, r)
            rows.append({"prompt_caching": caching, "case": i, "question": q, "route": r["kind"], "verified": r["verified"],
                         "pass": ok, "input_tokens": t["input_tokens"], "cached_tokens": t["cached_tokens"],
                         "cache_write_tokens": t["cache_write_tokens"], "output_tokens": t["output_tokens"],
                         "cost_usd": round(t["cost_usd"], 6), "tool_calls": len(r["tool_calls"]), "latency_s": r["latency_s"],
                         "answer_excerpt": (r["payload"].get("summary") or r["payload"].get("answer") or r["payload"].get("message") or "")[:200]})
            print(f"caching={caching!s:5} case {i:2} {'PASS' if ok else 'FAIL'} {t['input_tokens']:>6} in "
                  f"({t['cached_tokens']} cached) {t['output_tokens']:>5} out ${t['cost_usd']:.5f} {r['latency_s']}s")
            time.sleep(1)
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    for caching in (True, False):
        sub = [r for r in rows if r["prompt_caching"] == caching]
        print(f"\nprompt caching {'ON ' if caching else 'OFF'}: pass {sum(r['pass'] for r in sub)}/{len(sub)}, "
              f"avg cost ${sum(r['cost_usd'] for r in sub) / len(sub):.5f}, "
              f"cached share {sum(r['cached_tokens'] for r in sub) / max(sum(r['input_tokens'] for r in sub), 1):.0%}, "
              f"avg latency {sum(r['latency_s'] for r in sub) / len(sub):.1f}s")
    print(f"saved {out}")


if __name__ == "__main__":
    main()
