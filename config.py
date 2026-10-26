"""App-wide settings. Every cost-saving feature and safety limit is a constant here so it can be switched and compared."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

REPO_DIR = Path(__file__).resolve().parent
LOGS_DIR = REPO_DIR / "logs"
LIBRARY_DIR = REPO_DIR / "library"

# --- Model -------------------------------------------------------------------------------------
MODEL = "gpt-6-luna"  # the only model this app uses
PORTKEY_BASE_URL = "https://api.portkey.ai/v1"
MAX_OUTPUT_TOKENS = 2_500  # per model call

# Prices in USD per 1M tokens. Update with current course pricing (source: MGT 409 Lecture 11, OpenAI Standard).
PRICES = {"input": 0.10, "cached_input": 0.01, "cache_write": 0.125, "output": 0.50}

# --- Cost-saving switches (each can be turned off to measure its effect) -----------------------
PROMPT_CACHING = True  # static system prompts first + a stable prompt_cache_key per agent
ANSWER_CACHE = True  # exact-match cache of identical questions on an identical dashboard state
VERIFY_ONLY_WHEN_NEEDED = True  # skip the Verifier when a draft has no numbers and no citations
RETRIEVAL_TOP_K = 5
RETRIEVAL_MAX_WORDS = 300

# --- Safety limits -------------------------------------------------------------------------------
MAX_TOOL_CALLS_PER_RUN = 8
MAX_HOPS_PER_RUN = 4
RUN_TOKEN_CAP = 40_000
SESSION_TOKEN_CAP = 300_000
MAX_MESSAGE_CHARS = 2_000
RATE_LIMIT_PER_MINUTE = 10
INJECTION_SCREENING = True


def find_env_file(repo_dir: Path = REPO_DIR) -> Path | None:
    """Look for .env in the repo folder first, then in the folder one level above it."""
    for candidate in (repo_dir / ".env", repo_dir.parent / ".env"):
        if candidate.is_file():
            return candidate
    return None


def load_env(repo_dir: Path = REPO_DIR) -> Path | None:
    path = find_env_file(repo_dir)
    if path:
        load_dotenv(path, override=False)
    return path


ENV_FILE = load_env()


def api_settings() -> dict:
    """Portkey (course key) first; OPENAI_API_KEY only as a fallback. Returns kwargs for the OpenAI client."""
    portkey = os.getenv("PORTKEY_API_KEY", "").strip()
    if portkey:
        # force-refresh: never serve a stored gateway response, so token counts and latency are always real
        return {"api_key": portkey, "base_url": PORTKEY_BASE_URL,
                "default_headers": {"x-portkey-api-key": portkey, "x-portkey-cache-force-refresh": "true"}}
    openai_key = os.getenv("OPENAI_API_KEY", "").strip()
    if openai_key:
        return {"api_key": openai_key}
    raise RuntimeError("No API key found. Put PORTKEY_API_KEY in a .env file in this folder or the folder above it.")
