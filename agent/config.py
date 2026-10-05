"""Central configuration. Secrets come from environment variables only."""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
STATE = ROOT / "state"
DRAFTS = ROOT / "drafts"
IMAGES = ROOT / "images"
CAROUSELS = ROOT / "carousels"
FONTS = ROOT / "fonts"

for _d in (STATE, DRAFTS, IMAGES, CAROUSELS):
    _d.mkdir(parents=True, exist_ok=True)

# Load .env if python-dotenv is installed (optional).
try:  # pragma: no cover
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
except Exception:
    pass


def env(name: str, default: str | None = None, required: bool = False) -> str | None:
    val = os.environ.get(name, default)
    if required and not val:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return val


def mode() -> str:
    """'approve' (stage only) or 'auto' (publish after gates). MODE env overrides mode.txt."""
    m = os.environ.get("AGENT_MODE")
    if not m:
        f = ROOT / "mode.txt"
        m = f.read_text().strip() if f.exists() else "approve"
    m = m.lower()
    if m not in ("approve", "auto"):
        raise RuntimeError("mode must be 'approve' or 'auto'")
    return m


# Models
LLM_MODEL = env("LLM_MODEL", "claude-sonnet-5")
LLM_MODEL_FAST = env("LLM_MODEL_FAST", "claude-haiku-4-5-20251001")

# LinkedIn
LINKEDIN_API_VERSION = env("LINKEDIN_API_VERSION", "202601")  # YYYYMM; set to a currently supported version

# Apify actors and inputs (see docs/RUNBOOK.md). Keep counts small: pay-per-result.
APIFY_BASE = "https://api.apify.com/v2"
YOUTUBE_ACTOR = "streamers~youtube-scraper"
TIKTOK_ACTOR = "clockworks~tiktok-scraper"
INSTAGRAM_ACTOR = "apify~instagram-scraper"
INSTAGRAM_TAGS = ["ainews", "artificialintelligence", "aiagents", "openai", "chatgpt", "automation"]

MAX_REPLIES_PER_POST_PER_RUN = 3
TOPIC_WINDOW_DAYS = 14
