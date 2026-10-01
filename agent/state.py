"""JSON state files: published posts, rolling topics, discovery cache, drafts."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from . import config


def _read(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError:
        return default


def _write(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    tmp.replace(path)


def now() -> datetime:
    return datetime.now(timezone.utc)


# ---- published ----
def published() -> list[dict]:
    return _read(config.STATE / "published.json", [])


def add_published(record: dict) -> None:
    items = published()
    items.append(record)
    _write(config.STATE / "published.json", items)


def recent_published(days: int = 7) -> list[dict]:
    cutoff = now() - timedelta(days=days)
    out = []
    for r in published():
        try:
            ts = datetime.fromisoformat(r.get("publishedAt") or r["date"] + "T00:00:00+00:00")
        except Exception:
            continue
        if ts >= cutoff:
            out.append(r)
    return out


def posted_today() -> bool:
    today = now().date().isoformat()
    return any(r.get("date") == today for r in published())


# ---- topics (rolling window) ----
def topics() -> list[dict]:
    items = _read(config.STATE / "topics.json", [])
    cutoff = now() - timedelta(days=config.TOPIC_WINDOW_DAYS)
    keep = []
    for t in items:
        try:
            if datetime.fromisoformat(t["at"]) >= cutoff:
                keep.append(t)
        except Exception:
            continue
    return keep


def add_topic(topic: str, hook: str = "", visual: str = "", structure: str = "") -> None:
    items = topics()
    items.append({"topic": topic, "hook": hook, "visual": visual, "structure": structure, "at": now().isoformat()})
    _write(config.STATE / "topics.json", items)


# ---- discovery cache (shared by both lanes) ----
def save_discovery(items: list[dict]) -> None:
    _write(config.STATE / "discovery-latest.json", {"fetchedAt": now().isoformat(), "items": items})


def load_discovery_if_today() -> list[dict] | None:
    d = _read(config.STATE / "discovery-latest.json", None)
    if not d:
        return None
    try:
        fetched = datetime.fromisoformat(d["fetchedAt"]).astimezone().date()
    except Exception:
        return None
    if fetched == datetime.now().astimezone().date():
        return d["items"]
    return None


# ---- drafts / pending ----
def draft_path(lane: str, date: str | None = None) -> Path:
    date = date or now().date().isoformat()
    return config.DRAFTS / f"{date}-{lane}.json"


def save_draft(lane: str, draft: dict) -> Path:
    p = draft_path(lane, draft.get("date"))
    _write(p, draft)
    # human-readable twin
    md = p.with_suffix(".md")
    md.write_text(render_draft_md(draft))
    return p


def load_draft(lane: str, date: str | None = None) -> dict | None:
    p = draft_path(lane, date)
    return _read(p, None)


def render_draft_md(d: dict) -> str:
    lines = [f"# Draft {d.get('date')} ({d.get('lane')})", "", f"**Status:** {d.get('status')}", ""]
    lines += [f"**Topic:** {d.get('topic')}", f"**Why now:** {d.get('whyNow','')}", "", "## Caption", "", d.get("caption", ""), ""]
    if d.get("imagePath"):
        lines += [f"**Image:** {d['imagePath']}", f"**Image prompt:** {d.get('imagePrompt','')}", ""]
    if d.get("documentPath"):
        lines += [f"**Carousel PDF:** {d['documentPath']}", ""]
    lines += ["## Sources", ""] + [f"- {s.get('platform','')}: {s.get('url','')}" for s in d.get("sources", [])]
    if d.get("replies"):
        lines += ["", "## Drafted comment replies", ""]
        for r in d["replies"]:
            lines.append(f"- To **{r.get('author','')}** ({r.get('category','')}): {r.get('reply','')}")
    return "\n".join(lines) + "\n"
