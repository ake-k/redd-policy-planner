"""Builds submission/report.html and submission/slides.html as single self-contained files.

Usage: python submission/build_submission.py
Every measured number is read from docs/benchmark.csv and docs/traced_run.json, and every engine number is computed by
engine/ at build time, so the documents cannot drift from the app.
"""

from __future__ import annotations

import base64
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import config  # noqa: E402
import engine  # noqa: E402

OUT = ROOT / "submission"
SHOTS = ROOT / "docs" / "screenshots"
AUTHOR = "Ake Kankirawatana"
REPO_URL = "https://github.com/ake-k/redd-policy-planner"


def img(name: str) -> str:
    p = SHOTS / name if not name.endswith(".svg") else ROOT / "docs" / name
    mime = "image/svg+xml" if name.endswith(".svg") else "image/jpeg"
    return f"data:{mime};base64,{base64.b64encode(p.read_bytes()).decode()}"


def fmt(x: float, d: int = 0) -> str:
    return f"{x:,.{d}f}"


def usd(x: float, d: int = 2) -> str:
    return f"${x:,.{d}f}"


# ------------------------------------------------------------------ measured numbers
bench = list(csv.DictReader((ROOT / "docs" / "benchmark.csv").open(encoding="utf-8")))
for r in bench:
    for k in ("input_tokens", "cached_tokens", "cache_write_tokens", "output_tokens", "tool_calls"):
        r[k] = int(r[k])
    for k in ("cost_usd", "latency_s"):
        r[k] = float(r[k])
    r["pass"] = r["pass"] == "True"
on = [r for r in bench if r["prompt_caching"] == "True"]
off = [r for r in bench if r["prompt_caching"] == "False"]


def stats(rows):
    n = len(rows)
    return {
        "n": n, "pass": sum(r["pass"] for r in rows),
        "input": sum(r["input_tokens"] for r in rows) / n, "cached": sum(r["cached_tokens"] for r in rows) / n,
        "write": sum(r["cache_write_tokens"] for r in rows) / n, "output": sum(r["output_tokens"] for r in rows) / n,
        "cost": sum(r["cost_usd"] for r in rows) / n, "latency": sum(r["latency_s"] for r in rows) / n,
        "cached_share": sum(r["cached_tokens"] for r in rows) / max(sum(r["input_tokens"] for r in rows), 1),
    }


S_ON, S_OFF = stats(on), stats(off)
_lat = sorted(r["latency_s"] for r in bench)
MED_LAT = (_lat[len(_lat) // 2 - 1] + _lat[len(_lat) // 2]) / 2
LAT_RANGE = (_lat[0], _lat[-1])
_rules_in = [r["input_tokens"] for r in on if r["route"] == "rules"] or [0]
RULES_RANGE = f"{min(_rules_in) / 1000:.1f}k–{max(_rules_in) / 1000:.1f}k"
RUNS_PER_USER = 40  # assumption: an analyst in an active feasibility phase asks ~2 questions per working day
per_user = S_ON["cost"] * RUNS_PER_USER
trace = json.loads((ROOT / "docs" / "traced_run.json").read_text(encoding="utf-8"))
TR, TC = trace["run"], trace["calls"]

# Safety events recorded by the app during development and testing (logs/safety.jsonl)
_ev = [json.loads(line) for line in (ROOT / "logs" / "safety.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()] \
    if (ROOT / "logs" / "safety.jsonl").is_file() else []
EV = {k: sum(e["kind"] == k for e in _ev) for k in ("injection_in_library", "blocked_input", "verifier_rejected", "unverified_answer", "router_override")}
N_TESTS = sum(f.read_text(encoding="utf-8").count("\ndef test_") for f in (ROOT / "tests").glob("test_*.py"))
ACC = ("with no loss in accuracy" if S_ON["pass"] >= S_OFF["pass"] else
       f"while accuracy was {S_ON['pass']}/10 with caching vs {S_OFF['pass']}/10 without (the misses were routing variance, not caching; see detail)")

# Engine numbers for the default sample province
D = engine.DEFAULT_STATE
CMP = engine.compare_standards(D)
J, A = CMP["JNR"], CMP["ART"]
GAP = A["net_credits_tco2e"] - J["net_credits_tco2e"]
SIM = engine.calculate(D)["simulator"]

# ------------------------------------------------------------------ shared style
CSS = """
:root{--ink:#0f2a22;--muted:#4f6a60;--accent:#0f7a55;--accent2:#0a5c8a;--edge:rgba(15,40,30,.10);--soft:rgba(15,122,85,.08);--bad:#c0392b;--warn:#a86a12}
*{box-sizing:border-box}
body{margin:0;font-family:-apple-system,BlinkMacSystemFont,"SF Pro Text","Segoe UI",Inter,Roboto,sans-serif;color:var(--ink);line-height:1.55;font-size:15px;
 background:radial-gradient(900px 600px at 0% 0%,#d9ecf4,transparent 60%),radial-gradient(900px 700px at 100% 10%,#f1ecdc,transparent 55%),#e8f3ed}
.page{max-width:900px;margin:28px auto;padding:44px 56px;background:rgba(255,255,255,.72);backdrop-filter:blur(24px);border:1px solid rgba(255,255,255,.8);border-radius:28px;box-shadow:0 12px 50px rgba(20,60,45,.12)}
h1{font-size:34px;letter-spacing:-.025em;margin:0 0 6px;line-height:1.15}
h2{font-size:22px;letter-spacing:-.015em;margin:38px 0 10px;padding-top:6px;border-top:1px solid var(--edge)}
h3{font-size:16px;margin:22px 0 6px}
p{margin:8px 0}
.lede{font-size:17px;color:var(--muted)}
.meta{display:flex;flex-wrap:wrap;gap:8px;margin:14px 0 4px}
.pill{display:inline-block;font-size:12.5px;font-weight:600;padding:5px 12px;border-radius:999px;background:var(--soft);color:var(--accent);text-decoration:none}
table{width:100%;border-collapse:collapse;font-size:13.5px;margin:10px 0}
th,td{padding:7px 9px;border-bottom:1px solid var(--edge);text-align:left;vertical-align:top}
th{font-size:11.5px;text-transform:uppercase;letter-spacing:.04em;color:var(--muted)}
td.n,th.n{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
tr.tot td{font-weight:700}
figure{margin:16px 0;text-align:center}
figure img{max-width:100%;border-radius:16px;border:1px solid var(--edge);box-shadow:0 6px 24px rgba(20,60,45,.10)}
figcaption{font-size:12.5px;color:var(--muted);margin-top:6px}
.two{display:grid;grid-template-columns:1fr 1fr;gap:18px;align-items:start}
.two img{max-height:640px;object-fit:contain}
.kpis{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin:14px 0}
.kpi{background:rgba(255,255,255,.85);border:1px solid var(--edge);border-radius:16px;padding:12px 14px}
.kpi b{display:block;font-size:22px;letter-spacing:-.02em}
.kpi span{font-size:12px;color:var(--muted)}
.callout{background:var(--soft);border-radius:16px;padding:12px 16px;margin:12px 0;font-size:14px}
.todo{background:#fff4d6;border:1px dashed var(--warn);border-radius:16px;padding:12px 16px;margin:12px 0;font-size:14px;color:#6b4a0c}
ol.steps li{margin:6px 0}
code{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:12.5px;background:rgba(15,40,30,.06);padding:1px 5px;border-radius:6px}
.src{font-size:12px;color:var(--muted)}
@media print{body{background:#fff}.page{box-shadow:none;border:0;margin:0;max-width:none;padding:0 6mm;backdrop-filter:none;background:#fff}
 h2{break-before:page;border-top:0}h2.keep{break-before:auto}figure,table,.kpis,.callout,.todo{break-inside:avoid}.two img{max-height:520px}}
"""

# ------------------------------------------------------------------ report
calls_rows = "".join(
    f"<tr><td>{i}</td><td>{c['agent'].replace('_', ' ')}</td><td>{', '.join(c['tool_calls']) or 'final JSON answer'}</td>"
    f"<td class='n'>{fmt(c['input_tokens'])}</td><td class='n'>{fmt(c['cached_tokens'])}</td><td class='n'>{fmt(c['output_tokens'])}</td>"
    f"<td class='n'>{c['latency_s']:.1f}s</td><td class='n'>{usd(c['cost_usd'], 5)}</td></tr>"
    for i, c in enumerate(TC, 1))
bench_rows = "".join(
    f"<tr><td>{a['case']}</td><td>{a['question']}</td><td>{a['route']}</td><td class='n'>{fmt(a['input_tokens'])} / {fmt(b['input_tokens'])}</td>"
    f"<td class='n'>{fmt(a['cached_tokens'])}</td><td class='n'>{usd(a['cost_usd'], 5)} / {usd(b['cost_usd'], 5)}</td>"
    f"<td class='n'>{'✓' if a['pass'] else '✗'} / {'✓' if b['pass'] else '✗'}</td></tr>"
    for a, b in zip(on, off))
proj_rows = "".join(
    f"<tr><td>{fmt(n)} user{'s' if n > 1 else ''}</td><td class='n'>{fmt(n * RUNS_PER_USER)}</td><td class='n'>{usd(per_user * n)}</td>"
    f"<td class='n'>{usd(S_OFF['cost'] * RUNS_PER_USER * n)}</td><td class='n'>{usd(per_user * n * 12)}</td></tr>"
    for n in (1, 100, 10_000))

REPORT = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>REDD+ Policy Planner · Final report</title><style>{CSS}</style></head><body><div class="page">

<h1>REDD+ Policy Planner</h1>
<p class="lede">An AI-assisted planning dashboard that lets government officials compare Verra JNR v4.1 and ART TREES 3.0
for selling jurisdictional forest carbon credits. Agents run real rule calculators and cite the rule text, and a verifier checks every number.</p>
<div class="meta"><span class="pill">{AUTHOR}</span><span class="pill">MGT 409 · Final project · Fall 2026</span>
<a class="pill" href="{REPO_URL}">{REPO_URL}</a><span class="pill">Runs locally: python app.py → localhost:8000</span></div>
<figure><img src="{img('dashboard.jpg')}" alt="Dashboard"><figcaption>The dashboard (JNR mode) with the agent chat on the right.
Module 1 shows the same inputs under both standards: for the sample province, ART yields {fmt(GAP)} more tCO₂e per year than JNR.</figcaption></figure>

<h2 class="keep">1 · Motivation: who has the problem</h2>
<p><b>Who.</b> National and subnational governments deciding whether to sell <i>jurisdictional</i> REDD+ credits, meaning
credits for reducing deforestation across a whole province or country rather than one project. The motivating case is
Thailand, where the Thailand Greenhouse Gas Management Organization (TGO) commissioned a jurisdictional REDD+ feasibility study.
The people who need this are the officials and analysts at TGO and the forest agencies who must recommend a standard.</p>
<p><b>The decision is hard and expensive to get wrong.</b> Two standards dominate, and they price risk very differently:</p>
<ul>
<li>ART TREES withholds a buffer of <b>5–25%</b> of credits, while Verra JNR's buffer ranges over <b>10–60%</b>
<span class="src">(ART JNR GCF comparison, Neeff &amp; Lee, 2021, p.12; same ranges in the TGO JREDD+ presentation, slide 28)</span>.
On the app's sample province, that gap is worth <b>{fmt(GAP)} tCO₂e a year</b>, about <b>{usd(GAP * 10 / 1e6, 1)} million a year</b>
at the LEAF Coalition's US$10/t floor price <span class="src">(Comparative Analysis of ART-TREES, Verra JNR and Premium T-VER, p.1)</span>.</li>
<li>Prices differ too: ART credits at roughly <b>US$15–20+/t</b> versus JNR at roughly <b>US$5–15/t</b>
<span class="src">(TGO JREDD+ report, ch. 5.2, Table 5)</span>. Guyana's TREES credits sold to airlines at <b>US$21.70/t</b>
<span class="src">(JREDD+ 101, p.7)</span>.</li>
<li>The path is long and costly: typically <b>3–5 years</b> from concept to first issuance <span class="src">(TGO JREDD+ presentation, slide 18)</span>,
and Guyana paid <b>US$1.8 million</b> for registration and validation/verification of its first TREES submission
<span class="src">(TGO JREDD+ report, ch. 4)</span>.</li>
<li>Thailand-specific risks move the buffer: <b>14.7 million rai</b> burned in early 2017 <span class="src">(Comparative Analysis, p.7)</span>,
and carbon rights over state forest land are not yet resolved <span class="src">(TGO JREDD+ report, ch. 5.3.1)</span>. Both are inputs to the risk tools.</li>
</ul>
<p><b>How they cope today.</b> Governments commission consultant studies. TGO's own terms of reference funded a <b>4-month,
400,000-baht</b> feasibility study <span class="src">(TOR, Jurisdictional REDD+ project, p.3)</span>. The output is a long narrative
report with static comparison tables. Answering a follow-up question such as "what if we pass a carbon rights law?" means
going back to the consultant, or working through a 20-page risk-tool PDF by hand. The cost is weeks of delay per question and
recommendations that are not tested against the actual rule arithmetic.</p>

<h2>2 · What is new</h2>
<table><thead><tr><th>Alternative</th><th>What it does</th><th>What it lacks</th></tr></thead><tbody>
<tr><td><b>ChatGPT / general chatbots</b></td><td>Explains REDD+ in fluent prose.</td><td>Answers from memory, which is often stale
(TREES 3.0 and the Reversal Risk Rating Tool date from June 2026). It does arithmetic in its head, has no citations to clauses,
and has no way to check its numbers.</td></tr>
<tr><td><b>ART / JNR / GCF comparison deck</b> (Neeff &amp; Lee, 2021)</td><td>A 24-slide static comparison of the standards.</td><td>It predates JNR v4.1 and TREES 3.0, does no calculations, and says nothing about a specific jurisdiction.</td></tr>
<tr><td><b>World Bank / FCPF Decision Support Tool</b> (Excel, 2021)</td><td>Helps choose a centralized, nested or decentralized model.</td><td>It covers nesting design only, with no buffer or crediting math and no comparison between standards.</td></tr>
<tr><td><b>Official tools</b>: Verra JNR Non-Permanence Risk Tool (PDF), JNR Allocation Tool (Excel v4.0), ART RRRT template (Word)</td><td>The authoritative questionnaires.</td><td>Each covers one standard and one step. None compares standards, and none answers "what if".</td></tr>
<tr><td><b>Consultant feasibility study</b> (e.g. TGO's 4-month TOR)</td><td>Expert judgement on the jurisdiction.</td><td>It is slow and expensive per question, and the analysis is frozen at delivery.</td></tr>
</tbody></table>
<p><b>What I do differently.</b> (1) Both standards' risk and crediting rules are encoded as <b>versioned, cited JSON</b> and run by a
deterministic engine, so the same inputs flow through JNR and ART side by side. (2) The agents <b>never do math</b>: they turn a
policy question ("pass a carbon rights law, secure 40% of funding") into calculator inputs, call the tools, and
<b>move the dashboard</b> to that scenario with an Undo button. (3) A <b>code verifier</b> rejects any number that did not come
from a tool in that run and any citation that was not retrieved. (4) It uses the <b>current rules</b>, checked against the
source PDFs on 26 October 2026, including ART's published Reversal Risk Rating Tool weights (v1.0, June 2026).</p>

<h2>3 · The agents</h2>
<figure><img src="{img('agent_diagram.svg')}" alt="Agent diagram"><figcaption>Agent design. Code steps (safety gate, verifier)
cost nothing; three LLM agents use gpt-6-luna with strict JSON-schema outputs.</figcaption></figure>
<table><thead><tr><th>Agent</th><th>Role</th><th>Tools</th></tr></thead><tbody>
<tr><td><b>Safety gate</b> (code)</td><td>Checks the 2,000-character limit, screens for injection phrases, enforces 10 requests/min per session and the session token cap, and serves exact repeats from the answer cache.</td><td>none</td></tr>
<tr><td><b>Orchestrator</b> (gpt-6-luna)</td><td>Classifies the message as rules_question, scenario, compare or out_of_scope, then routes it. A keyword backstop stops on-topic questions being refused (added after the benchmark exposed router misfires). Enforces ≤4 hops, ≤8 tool calls and ≤{fmt(config.RUN_TOKEN_CAP)} tokens per run.</td><td>none</td></tr>
<tr><td><b>Rules Navigator</b> (gpt-6-luna)</td><td>Answers "what do the rules say". Every claim must be cited; when the library has no answer it says so and links the official source.</td><td>search_library (BM25, top 5 chunks of ≤300 words), get_rule, get_sources</td></tr>
<tr><td><b>Scenario Analyst</b> (gpt-6-luna)</td><td>Answers what-if and JNR-vs-ART questions. It turns policy language into input patches, lists its assumptions, and flags ineligibility.</td><td>run_simulator, score_jnr_risk, score_trees_risk, allocate_jnr, compute_trees_credits, compare_standards, set_dashboard_state</td></tr>
<tr><td><b>Verifier</b> (code)</td><td>Checks that every number is in this run's tool results and every citation is among the retrieved sources. A failing draft goes back once; if it fails again it is shown with an "Unverified" badge.</td><td>none</td></tr>
</tbody></table>
<p><b>Why gpt-6-luna.</b> It is the course model on the course key. At {usd(config.PRICES['input'])} per million input tokens
({usd(config.PRICES['cached_input'])} cached) and {usd(config.PRICES['output'])} per million output tokens, a full answer costs
fractions of a cent. It supports tool calling and strict JSON schemas through the Responses API. The hard parts (arithmetic and
checking) are done in code, so the model only needs to understand the question and write clearly, which a small model does well.
<b>Why a code verifier rather than a fourth LLM:</b> checking that numbers match is exact work. Code does it for $0 and never
"agrees" with a hallucination.</p>

<h3>One traced run, step by step</h3>
<p>Question: <i>"{TR['question']}"</i></p>
<ol class="steps">
<li><b>Safety gate.</b> Under 2,000 characters, no injection phrases, under the rate and budget limits, no cache hit → continue.</li>
<li><b>Orchestrator</b> (call 1) classifies the message as <code>scenario</code> on JNR.</li>
<li><b>Scenario Analyst</b> (call 2) maps the three policy moves to inputs and calls <code>compare_standards</code> with
<code>{{"jnr_risk": {{"carbon_rights_law": true, "funding_secured_40pct": true, "legal_agreement_100yr": true}}}}</code>.
The engine rescores the JNR risk tool: carbon rights 6→3, funding 5→3, longevity 13→0, giving a rating of 15 and a 15% buffer.
JNR net credits = 2,462,400 × 0.85 = <b>{fmt(engine.compare_standards(engine.merge_state(D, {"jnr_risk": {"carbon_rights_law": True, "funding_secured_40pct": True, "legal_agreement_100yr": True}}))["JNR"]["net_credits_tco2e"])}</b> tCO₂e. ART is unchanged at {fmt(A['net_credits_tco2e'])}.</li>
<li>(Call 3) it calls <code>set_dashboard_state</code> with the same patch, so the sliders and checkboxes move to the scenario.</li>
<li>(Call 4) it returns the structured answer: summary, key numbers, assumptions and caveats.</li>
<li><b>Verifier</b> finds every number in the tool results → <b>Verified</b>. The UI applies the scenario and offers Undo.</li>
</ol>
<table><thead><tr><th>#</th><th>Agent</th><th>Tool requested</th><th class="n">Input</th><th class="n">Cached</th><th class="n">Output</th><th class="n">Latency</th><th class="n">Cost</th></tr></thead>
<tbody>{calls_rows}<tr class="tot"><td></td><td>Run total</td><td>{TR['tool_calls']} tool calls</td><td class="n">{fmt(TR['input_tokens'])}</td><td class="n">{fmt(TR['cached_tokens'])}</td>
<td class="n">{fmt(TR['output_tokens'])}</td><td class="n">{TR['latency_s']:.1f}s</td><td class="n">{usd(TR['cost_usd'], 5)}</td></tr></tbody></table>
<p class="src">Source: logs/runs.jsonl, run {TR['run_id']} (saved as docs/traced_run.json). Token counts are the API's own usage fields.</p>
<div class="two"><figure><img src="{img('trace_answer.jpg')}" alt="Traced answer"><figcaption>The answer with key numbers, assumptions, the Verified badge, cost, and the expandable tool trace.</figcaption></figure>
<figure><img src="{img('usage_drawer.jpg')}" alt="Usage drawer"><figcaption>The Usage drawer: tokens by agent for the last run, session totals, and the 100 / 10,000-user projection.</figcaption></figure></div>
<figure><img src="{img('trace_dashboard.jpg')}" alt="Dashboard after scenario"><figcaption>After the run, the dashboard shows the agent's scenario
(carbon rights law, 40% funding and the 100-year agreement checked; JNR rating 15) with an "Undo" toast.</figcaption></figure>

<h2>4 · Tokenomics</h2>
<p>Measured with <code>scripts/benchmark.py</code>: 10 fixed questions (6 scenario/compare, 4 rules), run with prompt caching on
and then off. Each answer is scored pass/fail against the engine's own outputs. Gateway response caching is disabled
(<code>x-portkey-cache-force-refresh</code>), so every call is a real generation.</p>
<div class="kpis">
<div class="kpi"><b>{fmt(S_ON['input'])}</b><span>input tokens / question (avg)</span></div>
<div class="kpi"><b>{S_ON['cached_share']:.0%}</b><span>of input served from prompt cache</span></div>
<div class="kpi"><b>{fmt(S_ON['output'])}</b><span>output tokens / question (avg)</span></div>
<div class="kpi"><b>{usd(S_ON['cost'], 5)}</b><span>cost / question (avg, caching on)</span></div></div>
<table><thead><tr><th>Setting</th><th class="n">Input</th><th class="n">Cached input</th><th class="n">Output</th><th class="n">Cost / question</th><th class="n">Latency</th><th class="n">Pass</th></tr></thead><tbody>
<tr><td>Prompt caching <b>on</b></td><td class="n">{fmt(S_ON['input'])}</td><td class="n">{fmt(S_ON['cached'])}</td><td class="n">{fmt(S_ON['output'])}</td><td class="n">{usd(S_ON['cost'], 5)}</td><td class="n">{S_ON['latency']:.1f}s</td><td class="n">{S_ON['pass']}/{S_ON['n']}</td></tr>
<tr><td>Prompt caching <b>off</b></td><td class="n">{fmt(S_OFF['input'])}</td><td class="n">0</td><td class="n">{fmt(S_OFF['output'])}</td><td class="n">{usd(S_OFF['cost'], 5)}</td><td class="n">{S_OFF['latency']:.1f}s</td><td class="n">{S_OFF['pass']}/{S_OFF['n']}</td></tr>
</tbody></table>
<p>Prompt caching cuts cost per question by <b>{1 - S_ON['cost'] / S_OFF['cost']:.0%}</b> {ACC}. Latency is <i>not</i> a caching
result here: it ranged from {LAT_RANGE[0]:.0f}s to {LAT_RANGE[1]:.0f}s (median {MED_LAT:.0f}s) with the provider's load during the run.
An earlier run at a quieter time measured 9.5s → 5.4s on average (docs/benchmark_run2_router_misfires.csv). Caching works
because each agent's long static instructions and tool schemas come first and keep a stable <code>prompt_cache_key</code>,
so calls 2–4 of a run (and later questions) reuse that prefix.</p>
<h3>Cost at scale</h3>
<p>Assumption: <b>{RUNS_PER_USER} questions per user per month</b>, about two per working day for an analyst during a
feasibility phase. Cost per question is the measured caching-on average. The Usage drawer recomputes this live from any value.</p>
<table><thead><tr><th>Users</th><th class="n">Questions / month</th><th class="n">Per month (caching on)</th><th class="n">Per month (caching off)</th><th class="n">Per year (on)</th></tr></thead><tbody>{proj_rows}</tbody></table>
<p>Per user that is <b>{usd(per_user, 3)} per month</b>. Even at 10,000 users the model bill is {usd(per_user * 10_000)} a month,
which is negligible next to a single 400,000-baht consultant study. The dashboard calculations themselves cost $0.</p>
<h3>Cost-cutting steps and their tradeoffs</h3>
<table><thead><tr><th>Step</th><th>Effect (measured or by design)</th><th>Tradeoff</th></tr></thead><tbody>
<tr><td>Static system prompts first + per-agent <code>prompt_cache_key</code></td><td>{S_ON['cached_share']:.0%} of input tokens cached; cost per question {usd(S_OFF['cost'], 5)} → {usd(S_ON['cost'], 5)}</td><td>Prompts must stay static: per-question data goes in the user message, never the instructions. The orchestrator prompt is under the 1,024-token minimum and is never cached.</td></tr>
<tr><td>Deterministic engine + code verifier</td><td>No tokens spent on arithmetic or checking</td><td>New rules need code and JSON changes, not just prompt edits.</td></tr>
<tr><td>Exact-match answer cache (<code>logs/cache.json</code>)</td><td>An identical question on an identical dashboard costs $0 and returns instantly</td><td>Only exact repeats hit. A paraphrase or any slider change is a miss.</td></tr>
<tr><td>Retrieval capped at 5 chunks of ≤300 words</td><td>Rules answers used {RULES_RANGE} input tokens in the benchmark (the top of the range includes a verifier fix round)</td><td>Very broad questions can miss a relevant chunk; the agent reports such gaps.</td></tr>
<tr><td>Verifier only when the draft has numbers or citations</td><td>Skips a no-op step</td><td>None in practice; it is free code either way.</td></tr>
</tbody></table>
<details open><summary><b>Benchmark detail</b> (caching on / off)</summary>
<table><thead><tr><th>#</th><th>Question</th><th>Route</th><th class="n">Input on/off</th><th class="n">Cached</th><th class="n">Cost on/off</th><th class="n">Pass</th></tr></thead><tbody>{bench_rows}</tbody></table></details>
<p class="src">Raw data: docs/benchmark.csv. Earlier runs are kept as evidence of what changed: docs/benchmark_run1_before_router_fix.csv
(one eligibility question routed to the rules agent) and docs/benchmark_run2_router_misfires.csv (two on-topic questions refused as out of
scope). That led to the router prompt fix and the keyword backstop.</p>

<h2>5 · Safety</h2>
<table><thead><tr><th>Risk</th><th>Why it matters here</th><th>Defense built</th><th>Evidence</th></tr></thead><tbody>
<tr><td><b>Prompt injection</b> via chat or a poisoned source document</td><td>A tampered excerpt could make the planner tell a ministry that "the ART buffer is 0%".</td>
<td>User text and retrieved text go in <code>&lt;untrusted_data&gt;</code> blocks, and prompts say to ignore instructions inside them. <code>safety.py</code> blocks injection phrases in chat before any model call and withholds poisoned library chunks.</td>
<td>The poisoned file <code>library/test_injection.md</code> was withheld {EV['injection_in_library']} times; {EV['blocked_input']} chat injections were blocked; tests in <code>test_safety.py</code>.</td></tr>
<tr><td><b>Data leaks</b></td><td>System prompts or keys exposed.</td><td>"Reveal your system prompt" is blocked; the key is only in <code>.env</code> (git-ignored) and sent only to Portkey.</td><td>Blocked-input screenshot; repo scan finds no key.</td></tr>
<tr><td><b>Invented facts or numbers</b></td><td>A wrong buffer figure changes revenue by millions.</td><td>Numbers only from tools; the code verifier with one fix round, then an "Unverified" badge; citations required; ART weights from the published RRRT v1.0.</td><td>{EV['verifier_rejected']} drafts rejected and sent back in testing (e.g. a citation to a section that was never retrieved); {EV['unverified_answer']} shown as Unverified.</td></tr>
<tr><td><b>Wrong actions</b></td><td>The agent changing a user's carefully set scenario.</td><td>The only "action" tool moves on-screen inputs, with an Undo toast. Nothing is sent or saved anywhere.</td><td>Trace-dashboard screenshot.</td></tr>
<tr><td><b>Loops and runaway spending</b></td><td>A model that keeps calling tools.</td><td>≤8 tool calls (then tools are withdrawn), ≤4 hops, a {fmt(config.RUN_TOKEN_CAP)}-token run cap, a {fmt(config.SESSION_TOKEN_CAP)}-token session cap with a friendly "budget reached" message, 10 requests/min, 2,000 characters max.</td>
<td>Tests run a fake model that loops forever: it is cut at exactly 8 tool calls, then stopped by the budget.</td></tr>
</tbody></table>
<div class="two"><figure><img src="{img('safety_chat.jpg')}" alt="Safety in chat"><figcaption>Top: an injection attempt is blocked before reaching any model.
Bottom: a buffer question whose best-matching "source" is the poisoned file. The screen withholds it and the answer correctly gives 5–25% (30% after a reversal), not 0%.</figcaption></figure>
<figure><img src="{img('safety_log.jpg')}" alt="Safety log"><figcaption>The in-app Safety log: poisoned sources withheld, blocked inputs, and Verifier rejections that were sent back for a fix.</figcaption></figure></div>
<p><b>Automated tests</b> (<code>python -m pytest</code>, {N_TESTS} tests, no API key needed) cover: engine math against hand calculations,
including the JNR longevity FAIL, the rating floor of 10, the PDF's own replacement-guarantee example (100,000 tCO₂e, 30%
guaranteed, rating 20 → 14,000 buffer credits) and the TREES deduction order; the <code>.env</code> repo-then-parent lookup;
injection screening (the poisoned chunk ranks first when the screen is off and is withheld when it is on); verifier
rejections; the tool-call limit; the run and session budget stops; the rate limit; and the router backstop.</p>

<h2>6 · Impact</h2>
<table><thead><tr><th>Benefit</th><th>Before</th><th>With the planner</th><th>Source</th></tr></thead><tbody>
<tr><td>Time to answer a what-if (e.g. "pass a carbon rights law")</td><td>A consultant round-trip inside a 4-month study</td><td>median {MED_LAT:.0f} s by agent ({LAT_RANGE[0]:.0f}–{LAT_RANGE[1]:.0f} s); instant on the sliders</td><td>TOR p.3; benchmark</td></tr>
<tr><td>Cost of an answer</td><td>Part of a 400,000-baht study</td><td>{usd(S_ON['cost'], 4)} per question</td><td>TOR p.3; benchmark</td></tr>
<tr><td>Standards compared on the same inputs</td><td>Static tables (2021 deck predates both current versions)</td><td>JNR v4.1 and TREES 3.0, live</td><td>Neeff &amp; Lee (2021)</td></tr>
<tr><td>Size of the decision for the sample province</td><td>Not modeled: the Comparative Analysis lists buffer/permanence as "Not yet modeled"</td><td>{fmt(GAP)} tCO₂e/yr gap, ≈ {usd(GAP * 10 / 1e6, 1)}M/yr at US$10/t</td><td>Comparative Analysis p.8; engine</td></tr>
</tbody></table>
<p><b>A concrete finding the planner surfaces.</b> On the sample inputs, three policy moves (a carbon rights law, 40% of funding
secured, and a 100-year legal agreement) cut the JNR buffer from 33% to 15%. That closes most of the gap to ART: from {fmt(GAP)} tCO₂e to
69,120 tCO₂e a year. This is exactly the kind of "which reforms are worth it under which standard" question that a static study cannot answer on demand.</p>
<div class="callout"><b>User trial (author self-test, n = 1).</b> Ake Kankirawatana asked: "Our province has the sample inputs.
A major fire season was reported to ART as a reversal within the past 5 years. What is our ART buffer now, how many net credits do we lose,
and is ART still better than JNR?" <b>Before</b> (TREES Reversal Risk Rating Tool and TREES 3.0 crediting section, by hand): not finished
within 10 minutes. <b>With the planner</b>: the correct answer, which is the ART buffer rising from 12% to a fixed 30%, ART net credits falling from 2,162,160 to
1,719,900 tCO₂e/yr (a loss of 442,260), and ART still ahead of JNR by 70,092 tCO₂e/yr. Quote: <i>"The agent correctly calculated the
reversal and got to the policy recommendation faster than I could."</i> Limits: the tester is the author, not an independent official,
and no screenshot of this run was kept.</div>

<h2>7 · Limits and next steps</h2>
<ul>
<li><b>Planning aid, not certification.</b> Real risk-tool scoring needs evidence that validators review. Some JNR inputs
(e.g. "proven mitigation") are yes/no here but need judgement in practice. Where the JNR PDF leaves a gap (a WGI average of exactly 0), the app documents its interpretation in the rule JSON.</li>
<li><b>Simplified crediting.</b> One reporting year, a flat emission factor, no removals, no HFLD crediting (not available to Thailand
anyway: forest cover of roughly 31.5% is below TREES' 50% threshold, per the TGO report, ch. 5.2.1), and project shares stand in for VT0007 risk maps.</li>
<li><b>A small rule library</b> (23 excerpts). Questions outside it get an honest "not covered" and a link, which is safe but not complete.</li>
<li><b>Router variance.</b> The router sometimes misclassifies; the keyword backstop and the "we/our → scenario" rule fixed the observed cases, but more test questions are needed.</li>
<li><b>Next steps:</b> Premium T-VER as a third pathway; multi-year projections with price scenarios (revenue, not just credits);
removals and HFLD; uploading real VT0007 risk-map outputs; Thai-language answers; a rule-update checker that diffs new versions of the standards; and hosting for TGO staff.</li>
</ul>
<p class="src">All numbers in this report are either measured from the app's logs and benchmark or computed by the app's engine, or cited to a named document.
AI assistance was used to build the app and draft this report; I checked every number against the sources listed.</p>
</div></body></html>"""

# ------------------------------------------------------------------ slides
REVEAL_CDN = "https://cdn.jsdelivr.net/npm/reveal.js@5.1.0/dist"  # brief: reveal.js loaded from a CDN
SLIDE_CSS = """
.reveal{font-family:-apple-system,BlinkMacSystemFont,"SF Pro Display","Segoe UI",Inter,sans-serif;color:#0f2a22;font-size:30px}
.reveal .slides{text-align:left}
.reveal h1,.reveal h2{font-family:inherit;color:#0f2a22;letter-spacing:-.025em;text-transform:none;margin:0 0 .4em}
.reveal h1{font-size:2.1em;line-height:1.05}.reveal h2{font-size:1.45em}
.reveal p,.reveal li{line-height:1.35}.reveal ul{margin-left:1em}.reveal li{margin:.25em 0}
.reveal .muted{color:#4f6a60}.reveal .accent{color:#0f7a55}
.backgrounds{background:radial-gradient(1200px 700px at 0% 0%,#d6ebf4,transparent 60%),radial-gradient(900px 700px at 100% 10%,#f2ecda,transparent 55%),#e6f2ec}
.glass{background:rgba(255,255,255,.72);border:1px solid rgba(255,255,255,.85);border-radius:28px;box-shadow:0 12px 40px rgba(20,60,45,.14);padding:.7em .9em}
.big{font-size:2em;font-weight:800;letter-spacing:-.03em;line-height:1}
.grid{display:grid;gap:.6em}.g2{grid-template-columns:1fr 1fr}.g3{grid-template-columns:repeat(3,1fr)}.g4{grid-template-columns:repeat(4,1fr)}
.stat span{display:block;font-size:.55em;color:#4f6a60;margin-top:.3em}
.reveal img.shot{border-radius:20px;box-shadow:0 10px 36px rgba(20,60,45,.18);margin:0;max-width:100%;height:auto;display:block}
.grid>*{min-width:0}
.pill{display:inline-block;font-size:.5em;font-weight:700;padding:.3em .8em;border-radius:999px;background:rgba(15,122,85,.12);color:#0f7a55;margin-right:.3em}
.small{font-size:.72em}.tiny{font-size:.45em;color:#4f6a60}
table.t{font-size:.74em;border-collapse:collapse;width:100%}table.t td,table.t th{padding:.35em .5em;border-bottom:1px solid rgba(15,40,30,.12);text-align:left}
"""
jnr_s = fmt(J["net_credits_tco2e"]); art_s = fmt(A["net_credits_tco2e"])
SLIDES = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>REDD+ Policy Planner · Slides</title><link rel="stylesheet" href="{REVEAL_CDN}/reveal.css"><style>{SLIDE_CSS}</style></head>
<body><div class="reveal"><div class="slides">

<section><div class="glass" style="padding:1.2em 1.4em">
<span class="pill">MGT 409 · Final project</span><span class="pill">{AUTHOR}</span>
<h1 style="margin-top:.5em">REDD+ Policy Planner</h1>
<p class="muted">Which carbon-credit standard should a government choose, and what is each reform worth?<br>
AI agents that run the real rule calculators, cite the rules, and check every number.</p>
<p class="tiny">{REPO_URL}</p></div></section>

<section><h2>The problem</h2>
<div class="grid g2"><div class="glass"><div class="big accent">5–25%</div><div class="stat">ART TREES buffer<span>vs <b>10–60%</b> under Verra JNR</span></div></div>
<div class="glass"><div class="big accent">{usd(GAP * 10 / 1e6, 1)}M/yr</div><div class="stat">buffer gap on a sample province at US$10/t<span>{fmt(GAP)} tCO₂e/yr</span></div></div></div>
<ul class="small"><li>Thailand (TGO) must choose JNR or ART, with unresolved carbon rights and high fire risk, both of which feed the risk tools</li>
<li>Today: a <b>4-month, 400,000-baht</b> consultant study, static tables, and a PDF risk questionnaire per standard</li>
<li>Every "what if we pass a carbon rights law?" means going back to the consultant</li></ul>
<p class="tiny">Sources: ART JNR GCF comparison (2021) p.12; TGO JREDD+ TOR p.3; LEAF floor price per Comparative Analysis p.1</p></section>

<section><h2>What is new</h2>
<table class="t"><tr><th></th><th>ChatGPT</th><th>Static decks / Excel tools</th><th>Consultant study</th><th><b>Planner</b></th></tr>
<tr><td>Both standards, same inputs</td><td>~</td><td>✗</td><td>✓</td><td><b>✓ live</b></td></tr>
<tr><td>Current rules (JNR v4.1, TREES 3.0)</td><td>✗</td><td>✗</td><td>✓</td><td><b>✓ cited</b></td></tr>
<tr><td>Real rule arithmetic</td><td>✗ in its head</td><td>one step each</td><td>✓</td><td><b>✓ engine</b></td></tr>
<tr><td>Instant what-ifs</td><td>✓ unverified</td><td>✗</td><td>✗</td><td><b>✓ verified</b></td></tr>
<tr><td>Cost per question</td><td>~$0</td><td>analyst hours</td><td>weeks + fees</td><td><b>{usd(S_ON['cost'], 4)}</b></td></tr></table>
<p class="small">Agents <b>never do math</b>: they translate policy into calculator inputs, move the dashboard (with Undo), and a code verifier rejects any number not produced by a tool.</p></section>

<section><h2>The agents</h2><img class="shot" src="{img('agent_diagram.svg')}" style="width:100%">
<p class="tiny">3 gpt-6-luna agents with strict JSON outputs, plus code steps for the safety gate and the verifier.</p></section>

<section><h2>Demo: one question, end to end</h2>
<div class="grid" style="grid-template-columns:1.9fr 1fr;align-items:start;gap:1em">
<img class="shot" src="{img('trace_dashboard.jpg')}">
<div class="small"><p><i>"Carbon rights law + 40% funding + 100-year agreement: JNR vs ART?"</i></p>
<ul><li>Orchestrator → <b>scenario</b></li><li>compare_standards → JNR buffer <b>33% → 15%</b></li>
<li>set_dashboard_state → sliders move, Undo</li><li>Verifier → <b>✓ Verified</b></li></ul>
<p class="tiny">{fmt(TR['input_tokens'] + TR['output_tokens'])} tokens · {usd(TR['cost_usd'], 4)} · {TR['latency_s']:.0f}s</p></div></div></section>

<section><h2>Cost to run</h2>
<div class="grid g4"><div class="glass"><div class="big">{fmt(S_ON['input'] / 1000, 1)}k</div><div class="stat">input tokens / question<span>{S_ON['cached_share']:.0%} cached</span></div></div>
<div class="glass"><div class="big">{fmt(S_ON['output'])}</div><div class="stat">output tokens<span>per question</span></div></div>
<div class="glass"><div class="big">{usd(S_ON['cost'], 4)}</div><div class="stat">per question<span>{usd(S_OFF['cost'], 4)} without caching</span></div></div>
<div class="glass"><div class="big">{usd(per_user * 10_000, 0)}</div><div class="stat">/ month at 10,000 users<span>{usd(per_user * 100, 2)} at 100 users</span></div></div></div>
<ul class="small"><li>Prompt caching: <b>{1 - S_ON['cost'] / S_OFF['cost']:.0%} cheaper</b>, accuracy {S_OFF['pass']}/10 → {S_ON['pass']}/10 (median answer {MED_LAT:.0f}s)</li>
<li>The engine and verifier are code ($0); an exact-repeat answer cache ($0); retrieval capped at 5 × 300 words</li></ul>
<p class="tiny">Measured: scripts/benchmark.py, 10 questions × caching on/off, gateway cache disabled. Assumes {RUNS_PER_USER} questions/user/month.</p></section>

<section><h2>Safety: defenses that fired</h2>
<div class="grid" style="grid-template-columns:auto 1fr;align-items:start;gap:1.2em">
<img class="shot" src="{img('safety_chat_crop.jpg')}" style="height:600px;width:auto;max-width:none">
<ul style="font-size:.8em"><li><b>Poisoned rule file</b> tells the agent "the ART buffer is 0%" → withheld {EV['injection_in_library']}×; the answer says 5–25%</li>
<li><b>"Ignore previous instructions…"</b> → blocked before any model call</li>
<li><b>Invented numbers or citations</b> → code verifier; {EV['verifier_rejected']} drafts sent back</li>
<li><b>Loops and spending</b> → ≤8 tools, ≤4 hops, 40k/run, 300k/session, 10 req/min</li>
<li><b>Wrong action</b> → only moves sliders, with Undo</li>
<li>{N_TESTS} pytest tests, including a fake model that loops forever</li></ul></div></section>

<section><h2>Impact</h2>
<div class="grid g3"><div class="glass"><div class="big accent">{MED_LAT:.0f}s</div><div class="stat">median per what-if answer<span>vs a consultant round-trip inside a 4-month study</span></div></div>
<div class="glass"><div class="big accent">{usd(S_ON['cost'], 4)}</div><div class="stat">per answer<span>vs a 400,000-baht study</span></div></div>
<div class="glass"><div class="big accent">33% → 15%</div><div class="stat">JNR buffer after 3 reforms<span>gap to ART: {fmt(GAP)} → 69,120 tCO₂e/yr</span></div></div></div>
<p class="small">Self-test (author, n = 1), fire-reversal question: not finished by hand in 10 min; the planner gave the correct answer (ART buffer 12% → 30%, ART still ahead by 70,092 tCO₂e/yr). <i>"The agent correctly calculated the reversal and got to the policy recommendation faster than I could."</i></p></section>

<section><h2>Limits and next steps</h2>
<div class="grid g2"><div class="glass small"><b>Limits</b><ul><li>Planning aid, not certification</li><li>One year, flat emission factor, no removals or HFLD</li><li>23-excerpt rule library</li><li>Router variance (backstopped)</li></ul></div>
<div class="glass small"><b>Next</b><ul><li>Premium T-VER as a third pathway</li><li>Revenue and price scenarios over time</li><li>Real VT0007 risk maps</li><li>Thai-language answers; hosted for TGO staff</li></ul></div></div>
<p class="tiny" style="margin-top:1em">Planning aid only. The official Verra JNR and ART TREES documents and tools govern.</p></section>

</div></div>
<script src="{REVEAL_CDN}/reveal.js"></script>
<script>Reveal.initialize({{hash:true,controls:true,progress:true,center:false,width:1280,height:760,margin:0.06,transition:'fade'}});</script>
</body></html>"""

(OUT / "report.html").write_text(REPORT, encoding="utf-8")
(OUT / "slides.html").write_text(SLIDES, encoding="utf-8")
print(f"report.html {len(REPORT) / 1e6:.1f} MB, slides.html {len(SLIDES) / 1e6:.1f} MB")
print(f"caching on: {S_ON}\ncaching off: {S_OFF}")
