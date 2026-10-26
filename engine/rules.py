"""Loads the versioned rule files in rules/. Rules live in JSON so they can be updated when a standard changes."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

RULES_DIR = Path(__file__).resolve().parent.parent / "rules"


@lru_cache(maxsize=None)
def load(rule_id: str) -> dict[str, Any]:
    path = RULES_DIR / f"{rule_id}.json"
    if not path.is_file():
        raise KeyError(f"unknown rule file: {rule_id}")
    return json.loads(path.read_text(encoding="utf-8"))


def all_rule_ids() -> list[str]:
    return sorted(p.stem for p in RULES_DIR.glob("*.json"))
