"""Trend discovery via Apify REST (run-sync-get-dataset-items). Token read from env only."""
from __future__ import annotations

import random
from datetime import datetime, timezone
from typing import Any

import requests

from . import config, state

TIMEOUT = 300


def _run(actor: str, body: dict) -> list[dict]:
    token = config.env("APIFY_TOKEN", required=True)
    url = f"{config.APIFY_BASE}/acts/{actor}/run-sync-get-dataset-items"
    r = requests.post(url, json=body, headers={"Authorization": f"Bearer {token}"}, timeout=TIMEOUT)
    r.raise_for_status()
    data = r.json()
    return data if isinstance(data, list) else []


def _age_hours(iso: str | None) -> float | None:
    if not iso:
        return None
    try:
        dt = datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return max((datetime.now(timezone.utc) - dt).total_seconds() / 3600, 0.5)
    except Exception:
        return None


def _num(*vals: Any) -> int:
    for v in vals:
        if isinstance(v, (int, float)):
            return int(v)
    return 0


def _norm(platform: str, raw: dict) -> dict | None:
    if platform == "youtube":
        posted = raw.get("date") or raw.get("uploadDate")
        item = dict(
            url=raw.get("url"), title=raw.get("title"), text=(raw.get("text") or raw.get("description") or "")[:1500],
            views=_num(raw.get("viewCount"), raw.get("views")), likes=_num(raw.get("likes")),
            comments=_num(raw.get("commentsCount")), shares=0, creator=raw.get("channelName"), posted=posted,
        )
    elif platform == "tiktok":
        item = dict(
            url=raw.get("webVideoUrl"), title=None, text=(raw.get("text") or "")[:1500],
            views=_num(raw.get("playCount")), likes=_num(raw.get("diggCount")),
            comments=_num(raw.get("commentCount")), shares=_num(raw.get("shareCount")),
            creator=(raw.get("authorMeta") or {}).get("name"), posted=raw.get("createTimeISO"),
        )
    else:  # instagram
        item = dict(
            url=raw.get("url"), title=None, text=(raw.get("caption") or "")[:1500],
            views=_num(raw.get("videoViewCount"), raw.get("videoPlayCount")), likes=_num(raw.get("likesCount")),
            comments=_num(raw.get("commentsCount")), shares=0, creator=raw.get("ownerUsername"),
            posted=raw.get("timestamp"),
        )
    if not item["url"]:
        return None
    item["platform"] = platform
    age = _age_hours(item["posted"])
    item["ageHours"] = age
    engagement = item["likes"] + 3 * item["comments"] + 4 * item["shares"] + item["views"] * 0.02
    item["engagement"] = int(engagement)
    item["velocity"] = round(engagement / age, 2) if age else None  # engagement per hour
    return item


def discover(force: bool = False) -> list[dict]:
    """Return normalized items. Reuses today's cache unless force=True (one scrape/day, both lanes)."""
    if not force:
        cached = state.load_discovery_if_today()
        if cached:
            return cached

    items: list[dict] = []
    errors: list[str] = []
    # Free actors only (YouTube + Instagram). TikTok actor is paid -> dropped.
    # Queries skew toward viral/trending AI news; the selector ranks by engagement velocity.
    jobs = [
        ("youtube", config.YOUTUBE_ACTOR, {
            "searchQueries": ["AI news this week", "AI agents", "OpenAI ChatGPT update", "AI automation business"],
            "dateFilter": "week", "maxResults": 12, "sortingOrder": "relevance"}),
        ("instagram", config.INSTAGRAM_ACTOR, {
            "directUrls": [f"https://www.instagram.com/explore/tags/{random.choice(config.INSTAGRAM_TAGS)}/"],
            "resultsType": "posts", "resultsLimit": 15, "onlyPostsNewerThan": "2 days"}),
    ]
    for platform, actor, body in jobs:
        try:
            for raw in _run(actor, body):
                n = _norm(platform, raw)
                if n:
                    items.append(n)
        except Exception as e:  # one platform failing must not kill the run
            errors.append(f"{platform}: {e}")

    if not items:
        raise RuntimeError("Discovery returned nothing. " + "; ".join(errors))
    if errors:
        print("[discovery] partial failures:", "; ".join(errors))
    state.save_discovery(items)
    return items
