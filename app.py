"""REDD+ Policy Planner. Run: python app.py, then open http://localhost:8000"""

from __future__ import annotations

import json
import os
import threading
from collections import defaultdict

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

import config
import engine
from agents import orchestrator, safety
from engine import jnr_risk, rules

app = FastAPI(title="REDD+ Policy Planner")
STATIC = config.REPO_DIR / "static"
app.mount("/static", StaticFiles(directory=STATIC), name="static")
PRESETS = json.loads((config.REPO_DIR / "data" / "presets.json").read_text(encoding="utf-8"))

limiter = safety.RateLimiter()
sessions: dict[str, dict] = defaultdict(lambda: {"tokens": 0, "cost_usd": 0.0, "runs": 0})
_session_lock = threading.Lock()


class CalcRequest(BaseModel):
    state: dict = Field(default_factory=dict)


class ChatRequest(BaseModel):
    session_id: str = Field(min_length=4, max_length=64)
    message: str
    state: dict = Field(default_factory=dict)


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


@app.get("/api/meta")
def meta():
    nprt, rrrt = rules.load("jnr_nprt_v4_1"), rules.load("trees_3_0_rrrt")
    return {
        "defaults": engine.DEFAULT_STATE,
        "presets": {name: engine.merge_state(engine.DEFAULT_STATE, {"jurisdiction": name, **p}) for name, p in PRESETS.items()},
        "jnr_risk_keys": list(jnr_risk.DEFAULTS),
        "nr": {"significance": nprt["natural_risk"]["significance_levels"], "likelihood": nprt["natural_risk"]["likelihood_levels"]},
        "rrrt": rrrt,
        "sources": rules.load("sources"),
        "badges": {
            "JNR": {"risk": f"{nprt['title']} {nprt['version']}", "allocation": "VT0007 v1.0-style allocation (Scenario 1)", "checked": nprt["last_checked"]},
            "ART": {"risk": f"{rrrt['title']} {rrrt['version'].split(',')[0]}", "allocation": "TREES 3.0 Section 10.4.1 credit calculation", "checked": rrrt["last_checked"]},
        },
        "limits": {"message_chars": config.MAX_MESSAGE_CHARS, "session_tokens": config.SESSION_TOKEN_CAP,
                   "run_tokens": config.RUN_TOKEN_CAP, "tool_calls": config.MAX_TOOL_CALLS_PER_RUN},
        "prices": config.PRICES,
        "model": config.MODEL,
    }


@app.post("/api/calc")
def calc(req: CalcRequest):
    try:
        out = engine.calculate(req.state)
        out["compare"] = engine.compare_standards(req.state)
        return out
    except (ValueError, KeyError) as e:
        raise HTTPException(status_code=422, detail=str(e))


@app.post("/api/chat")
def chat(req: ChatRequest):
    s = sessions[req.session_id]
    if not limiter.allow(req.session_id):
        safety.log_event("rate_limited", f"more than {config.RATE_LIMIT_PER_MINUTE} requests in a minute", req.session_id)
        return {"kind": "blocked", "payload": {"message": "Too many requests. Please wait a minute and try again."}, "session": s}
    if s["tokens"] >= config.SESSION_TOKEN_CAP:
        safety.log_event("budget_stop", f"session cap of {config.SESSION_TOKEN_CAP:,} tokens reached", req.session_id)
        return {"kind": "budget", "payload": {"message": "This session's AI budget is used up. The dashboard still works; start a new session to ask more."}, "session": s}
    try:
        state = engine.merge_state(engine.DEFAULT_STATE, req.state)
        engine.calculate(state)
    except (ValueError, KeyError) as e:
        raise HTTPException(status_code=422, detail=str(e))
    result = orchestrator.handle(req.message, state, req.session_id, s["tokens"])
    total = result["usage"]["total"]
    with _session_lock:
        s["tokens"] += total["input_tokens"] + total["output_tokens"]
        s["cost_usd"] += total["cost_usd"]
        s["runs"] += 1
    result["session"] = dict(s)
    return result


@app.get("/api/safety")
def safety_log():
    return {"events": safety.read_events()}


if __name__ == "__main__":
    print(f"REDD+ Policy Planner -> http://localhost:{os.getenv('PORT', '8000')}  (.env: {config.ENV_FILE or 'not found'})")
    uvicorn.run(app, host="127.0.0.1", port=int(os.getenv("PORT", "8000")), reload=False)
