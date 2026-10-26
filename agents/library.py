"""BM25 keyword search over library/*.md rule excerpts, with injection screening of every chunk."""

from __future__ import annotations

import math
import re
from collections import Counter
from functools import lru_cache

import config

from . import safety

_TOKEN = re.compile(r"[a-z0-9]+(?:\.[0-9]+)*")
STOPWORDS = set("the a an of to and or in on for is are be by with as at that this it from shall must any its their which what does say".split())


def _tokens(text: str) -> list[str]:
    return [t for t in _TOKEN.findall(text.lower()) if t not in STOPWORDS]


def _parse(path) -> dict:
    raw = path.read_text(encoding="utf-8")
    meta, body = {}, raw
    if raw.startswith("---"):
        _, front, body = raw.split("---", 2)
        for line in front.strip().splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                meta[k.strip()] = v.strip().strip('"')
    words = body.split()
    return {
        "id": meta.get("id", path.stem),
        "source": meta.get("source", ""),
        "standard": meta.get("standard", ""),
        "version": meta.get("version", ""),
        "section": meta.get("section", ""),
        "page": meta.get("page", ""),
        "text": " ".join(words[: config.RETRIEVAL_MAX_WORDS]),
    }


@lru_cache(maxsize=1)
def load_chunks() -> tuple[dict, ...]:
    return tuple(_parse(p) for p in sorted(config.LIBRARY_DIR.glob("*.md")))


def search_library(query: str, standard: str | None = None, k: int | None = None,
                   session_id: str = "", run_id: str = "") -> dict:
    k = k or config.RETRIEVAL_TOP_K
    chunks = [c for c in load_chunks() if not standard or standard == "any" or c["standard"] == standard]
    docs = [_tokens(f"{c['section']} {c['source']} {c['text']}") for c in chunks]
    if not docs:
        return {"results": [], "blocked": []}
    avgdl = sum(map(len, docs)) / len(docs)
    df = Counter(t for d in docs for t in set(d))
    n = len(docs)
    q = _tokens(query)
    scored = []
    for c, d in zip(chunks, docs):
        tf = Counter(d)
        s = 0.0
        for t in q:
            if t in tf:
                idf = math.log(1 + (n - df[t] + 0.5) / (df[t] + 0.5))
                s += idf * tf[t] * 2.2 / (tf[t] + 1.2 * (0.25 + 0.75 * len(d) / avgdl))
        if s > 0:
            scored.append((s, c))
    scored.sort(key=lambda x: -x[0])

    results, blocked = [], []
    for s, c in scored:
        if len(results) >= k:
            break
        if config.INJECTION_SCREENING and (hit := safety.find_injection(c["text"])):
            safety.log_event("injection_in_library", f"dropped chunk {c['id']}: “{hit}”", session_id, run_id, c["text"])
            blocked.append(c["id"])
            continue
        results.append({**c, "score": round(s, 2)})
    return {"results": results, "blocked": blocked}
