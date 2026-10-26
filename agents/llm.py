"""Model client, per-run context (budgets, tool log, token usage), and the generic tool-calling loop."""

from __future__ import annotations

import json
import threading
import time
import uuid
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any, Callable

from openai import OpenAI

import config

from . import safety

RUNS_LOG = config.LOGS_DIR / "runs.jsonl"
_lock = threading.Lock()


@lru_cache(maxsize=1)
def client() -> OpenAI:
    return OpenAI(timeout=120, **config.api_settings())


def cost_usd(uncached: int, cached: int, cache_write: int, output: int) -> float:
    p = config.PRICES
    return (uncached * p["input"] + cached * p["cached_input"] + cache_write * p["cache_write"] + output * p["output"]) / 1e6


@dataclass
class RunContext:
    session_id: str
    dashboard_state: dict
    question: str = ""
    session_tokens_before: int = 0
    run_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    calls: list[dict] = field(default_factory=list)  # one entry per model call
    tool_log: list[dict] = field(default_factory=list)  # every tool call with its full result
    hops: list[str] = field(default_factory=list)
    retrieved: list[dict] = field(default_factory=list)  # library chunks and rules the agents saw
    proposed_state: dict | None = None
    stopped: str | None = None

    @property
    def tokens(self) -> int:
        return sum(c["input_tokens"] + c["output_tokens"] for c in self.calls)

    def check_budget(self) -> None:
        if self.tokens >= config.RUN_TOKEN_CAP:
            raise safety.BudgetExceeded(f"run token cap of {config.RUN_TOKEN_CAP:,} reached")
        if self.session_tokens_before + self.tokens >= config.SESSION_TOKEN_CAP:
            raise safety.BudgetExceeded(f"session token cap of {config.SESSION_TOKEN_CAP:,} reached")

    def hop(self, agent: str) -> None:
        if len(self.hops) >= config.MAX_HOPS_PER_RUN:
            raise safety.BudgetExceeded(f"agent hop limit of {config.MAX_HOPS_PER_RUN} reached")
        self.hops.append(agent)

    def usage_summary(self) -> dict:
        by_agent: dict[str, dict] = {}
        for c in self.calls:
            a = by_agent.setdefault(c["agent"], {"calls": 0, "input_tokens": 0, "cached_tokens": 0, "output_tokens": 0, "cost_usd": 0.0})
            a["calls"] += 1
            for k in ("input_tokens", "cached_tokens", "output_tokens", "cost_usd"):
                a[k] += c[k]
        total = {k: sum(c[k] for c in self.calls) for k in ("input_tokens", "cached_tokens", "cache_write_tokens", "output_tokens", "cost_usd")}
        return {"by_agent": by_agent, "total": total, "tool_calls": len(self.tool_log), "hops": self.hops}


def _log_call(entry: dict) -> None:
    RUNS_LOG.parent.mkdir(parents=True, exist_ok=True)
    with _lock, RUNS_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def call_model(ctx: RunContext, agent: str, instructions: str, input_items: list, schema: dict,
               tools: list[dict] | None = None):
    """One model call with usage logging. Static instructions go first so the prefix can be cached."""
    ctx.check_budget()
    kwargs: dict[str, Any] = {
        "model": config.MODEL,
        "instructions": instructions,
        "input": input_items,
        "max_output_tokens": config.MAX_OUTPUT_TOKENS,
        "text": {"format": {"type": "json_schema", "name": f"{agent}_output", "schema": schema, "strict": True}},
    }
    if tools:
        kwargs["tools"] = tools
    if config.PROMPT_CACHING:
        kwargs["prompt_cache_key"] = f"redd-planner-{agent}"
    else:
        # A unique prefix defeats the provider's automatic prefix cache, for with/without comparisons.
        kwargs["instructions"] = f"[nonce {uuid.uuid4().hex}]\n" + instructions
    t0 = time.perf_counter()
    resp = client().responses.create(**kwargs)
    latency = time.perf_counter() - t0
    u = resp.usage
    details = getattr(u, "input_tokens_details", None)
    cached = int(getattr(details, "cached_tokens", 0) or 0)
    cache_write = int(getattr(details, "cache_write_tokens", 0) or 0)
    uncached = max(u.input_tokens - cached - cache_write, 0)
    tool_calls = [o.name for o in resp.output if o.type == "function_call"]
    entry = {
        "ts": safety.now_iso(), "type": "call", "run_id": ctx.run_id, "session_id": ctx.session_id, "agent": agent,
        "model": resp.model, "input_tokens": u.input_tokens, "cached_tokens": cached, "cache_write_tokens": cache_write,
        "output_tokens": u.output_tokens, "tool_calls": tool_calls, "latency_s": round(latency, 2),
        "cost_usd": cost_usd(uncached, cached, cache_write, u.output_tokens), "caching": config.PROMPT_CACHING,
    }
    ctx.calls.append(entry)
    _log_call(entry)
    return resp


def run_agent(ctx: RunContext, agent: str, instructions: str, user_text: str, schema: dict,
              tools: list[dict] | None = None, impls: dict[str, Callable[..., dict]] | None = None,
              history: list | None = None) -> tuple[dict, list]:
    """Tool loop: call the model, run any tools it asks for, repeat until it returns the structured answer."""
    items: list = list(history or []) + [{"role": "user", "content": user_text}]
    while True:
        # Once the tool limit is hit, tools are withdrawn so the model has to answer.
        resp = call_model(ctx, agent, instructions, items, schema, None if ctx.stopped else tools)
        calls = [o for o in resp.output if o.type == "function_call"]
        if not calls:
            text = resp.output_text
            try:
                return json.loads(text), items + [{"role": "assistant", "content": text}]
            except json.JSONDecodeError as e:
                raise RuntimeError(f"{agent} returned invalid JSON: {text[:200]}") from e
        items += [o.model_dump(exclude_none=True) for o in resp.output if o.type in ("function_call", "reasoning")]
        for call in calls:
            if len(ctx.tool_log) >= config.MAX_TOOL_CALLS_PER_RUN:
                ctx.stopped = f"tool-call limit of {config.MAX_TOOL_CALLS_PER_RUN} reached"
                safety.log_event("tool_limit", ctx.stopped, ctx.session_id, ctx.run_id)
                result = {"error": f"Tool-call limit reached ({config.MAX_TOOL_CALLS_PER_RUN}). Do not call more tools; answer now with what you have."}
            else:
                try:
                    args = json.loads(call.arguments or "{}")
                    result = (impls or {})[call.name](ctx, **args)
                except Exception as e:  # tool errors go back to the model, not to a crash
                    result = {"error": f"{type(e).__name__}: {e}"}
                ctx.tool_log.append({"agent": agent, "tool": call.name, "args": call.arguments, "result": result})
            items.append({"type": "function_call_output", "call_id": call.call_id, "output": json.dumps(result)})
