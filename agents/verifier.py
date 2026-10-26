"""Verifier: checks every number in a draft against this run's tool results, and every citation against retrieved sources.

It is deterministic code, not a model call: a check that numbers match is exact work, and code does it for free.
"""

from __future__ import annotations

import json
import re

_NUM = re.compile(r"(?<![\w.])[-−]?\d[\d,]*(?:\.\d+)?(?:\s*(?:million|m\b|k\b|thousand))?", re.I)
SMALL_INT_OK = 10  # counts like "3 categories" or "step 2" are not checked


def _parse(token: str) -> float | None:
    t = token.lower().replace(",", "").replace("−", "-").strip()
    mult = 1.0
    for word, m in (("million", 1e6), ("thousand", 1e3), ("m", 1e6), ("k", 1e3)):
        if t.endswith(word):
            t, mult = t[: -len(word)].strip(), m
            break
    try:
        return float(t) * mult
    except ValueError:
        return None


def numbers_in(text: str) -> list[tuple[str, float]]:
    out = []
    for m in _NUM.finditer(text):
        v = _parse(m.group(0))
        if v is not None:
            out.append((m.group(0).strip(), v))
    return out


def _collect(obj, acc: set[float]) -> None:
    if isinstance(obj, bool):
        return
    if isinstance(obj, (int, float)):
        acc.add(float(obj))
        acc.add(abs(float(obj)))
    elif isinstance(obj, str):
        acc.update(v for _, v in numbers_in(obj))
        acc.update(abs(v) for _, v in numbers_in(obj))
    elif isinstance(obj, dict):
        for v in obj.values():
            _collect(v, acc)
    elif isinstance(obj, list):
        for v in obj:
            _collect(v, acc)


def _matches(v: float, known: set[float]) -> bool:
    if abs(v) <= SMALL_INT_OK and float(v).is_integer():
        return True
    for k in known:
        tol = max(abs(k) * 0.006, 0.5)  # allows "about 2.46 million" for 2,462,400
        if abs(abs(v) - abs(k)) <= tol:
            return True
    return False


_SEC_NUM = re.compile(r"\d+(?:\.\d+)+|\b\d+\b")
_FAMILIES = ("trees", "jnr", "vt0007")


def _same_source(cited: str, retrieved: str) -> bool:
    a, b = cited.lower(), retrieved.lower()
    return a in b or b in a or any(f in a and f in b for f in _FAMILIES)


def _same_section(cited: str, retrieved: str) -> bool:
    """Match on text, or on section numbers where one is a sub-section of the other (7.1.1 within 7.1)."""
    a, b = cited.lower().strip(), retrieved.lower()
    if not a or a in b or b in a:
        return True
    nums_a, nums_b = _SEC_NUM.findall(a), _SEC_NUM.findall(b)
    return any(x == y or x.startswith(y + ".") or y.startswith(x + ".") for x in nums_a for y in nums_b) or \
        (not nums_a and any(w in b for w in a.split() if len(w) > 5))


def verify(draft: dict, tool_log: list[dict], retrieved: list[dict], question: str, dashboard_state: dict) -> dict:
    known: set[float] = set()
    for t in tool_log:
        _collect(t["result"], known)
    _collect(dashboard_state, known)
    _collect(question, known)
    problems: list[str] = []

    text = " ".join([draft.get("summary", ""), draft.get("answer", "")] + list(draft.get("assumptions", [])) + list(draft.get("caveats", [])))
    for token, v in numbers_in(text):
        if not _matches(v, known):
            problems.append(f"number “{token}” does not appear in any tool result from this run")
    for kn in draft.get("key_numbers", []):
        if not _matches(float(kn["value"]), known):
            problems.append(f"key number {kn['label']} = {kn['value']} does not appear in any tool result")

    for c in draft.get("citations", []):
        ok = any(_same_source(c.get("source", ""), r["source"]) and _same_section(c.get("section", ""), r["section"])
                 for r in retrieved if r["source"])
        if not ok:
            problems.append(f"citation “{c.get('source')} — {c.get('section')}” is not among the retrieved sources")
    if "citations" in draft and draft.get("answer") and not draft["citations"] and not draft.get("gaps"):
        problems.append("the answer makes claims but has no citations")
    # Report each problem once
    return {"approved": not problems, "problems": list(dict.fromkeys(problems))}


def needs_verification(draft: dict) -> bool:
    text = json.dumps(draft)
    return bool(draft.get("citations") or draft.get("key_numbers") or any(abs(v) > SMALL_INT_OK for _, v in numbers_in(text)))


def fix_request(problems: list[str]) -> str:
    return ("The Verifier rejected your draft:\n- " + "\n- ".join(problems) +
            "\nRevise it. Use only numbers and citations that appear in your tool results from this run "
            "(call a tool if you need a number you do not have). Return the same JSON shape.")
