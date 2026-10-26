"""Input limits, prompt-injection screening, rate limiting, budgets, and the safety log."""

from __future__ import annotations

import json
import re
import threading
import time
from collections import defaultdict, deque
from datetime import datetime, timezone

import config

SAFETY_LOG = config.LOGS_DIR / "safety.jsonl"
_lock = threading.Lock()

INJECTION_PATTERNS = [
    r"ignore\s+(all\s+|any\s+|the\s+)?(previous|prior|above|earlier)\s+(instructions|rules|prompts?)",
    r"disregard\s+(all\s+|any\s+|the\s+)?(previous|prior|above|earlier|your)\s+(instructions|rules|prompts?)",
    r"(reveal|show|print|repeat|output)\s+(me\s+)?(your|the)\s+(system\s+prompt|hidden\s+instructions|instructions)",
    r"\byou\s+are\s+now\b",
    r"\bnew\s+(system\s+)?instructions\s*:",
    r"\b(developer|jailbreak|dan)\s+mode\b",
    r"\bsystem\s+(override|note)\s*:",
    r"\bact\s+as\s+(an?\s+)?(unrestricted|different)\b",
]
_INJECTION_RE = [re.compile(p, re.I) for p in INJECTION_PATTERNS]


class BudgetExceeded(Exception):
    """Raised when a run or session goes over its token cap or tool-call limit."""


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def log_event(kind: str, detail: str, session_id: str = "", run_id: str = "", excerpt: str = "") -> dict:
    entry = {"ts": now_iso(), "kind": kind, "detail": detail, "session_id": session_id, "run_id": run_id,
             "excerpt": excerpt[:200]}
    SAFETY_LOG.parent.mkdir(parents=True, exist_ok=True)
    with _lock, SAFETY_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return entry


def read_events(limit: int = 100) -> list[dict]:
    if not SAFETY_LOG.is_file():
        return []
    lines = SAFETY_LOG.read_text(encoding="utf-8").splitlines()[-limit:]
    return [json.loads(line) for line in reversed(lines) if line.strip()]


def find_injection(text: str) -> str | None:
    """Return the first injection-looking phrase in text, or None."""
    for rx in _INJECTION_RE:
        m = rx.search(text)
        if m:
            return m.group(0)
    return None


def check_message(text: str) -> str | None:
    """Validate a user message. Returns a reason string if it must be blocked."""
    if not text.strip():
        return "empty message"
    if len(text) > config.MAX_MESSAGE_CHARS:
        return f"message is {len(text)} characters; the limit is {config.MAX_MESSAGE_CHARS}"
    if config.INJECTION_SCREENING and (hit := find_injection(text)):
        return f"possible prompt injection: “{hit}”"
    return None


def untrusted(label: str, text: str) -> str:
    """Wrap data in a clearly delimited block. System prompts say instructions inside these blocks are ignored."""
    return f"<untrusted_data source=\"{label}\">\n{text}\n</untrusted_data>"


class RateLimiter:
    def __init__(self, per_minute: int = config.RATE_LIMIT_PER_MINUTE):
        self.per_minute = per_minute
        self.hits: dict[str, deque] = defaultdict(deque)

    def allow(self, session_id: str) -> bool:
        now = time.monotonic()
        q = self.hits[session_id]
        while q and now - q[0] > 60:
            q.popleft()
        if len(q) >= self.per_minute:
            return False
        q.append(now)
        return True
