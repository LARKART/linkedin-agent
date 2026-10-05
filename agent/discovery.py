"""Trend discovery from FREE, keyless sources: Google News RSS + Hacker News (Algolia).

No Apify, no API keys. Both give recent, trending AI news; Hacker News adds real engagement
signals (points/comments) so the selector can rank by velocity. Optional: set USE_APIFY=true
to fall back to the old Apify actors if that account has credits.
"""
from __future__ import annotations

import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import quote

import requests

from . import config, state

UA = "Mozilla/5.0 (compatible; LarkAIAgent/1.0; +https://lark.ai)"
TIMEOUT = 45
NEWS_QUERIES = ["AI agents", "OpenAI", "ChatGPT", "artificial intelligence", "AI automation", "Anthropic Claude"]
HN_QUERIES = ["AI", "LLM", "agents", "OpenAI", "Anthropic"]


def _age_hours(dt: datetime | None) -> float | None:
    if not dt:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return max((datetime.now(timezone.utc) - dt).total_seconds() / 3600, 0.5)


def _finalize(item: dict) -> dict:
    age = item.get("ageHours")
    eng = item["likes"] + 3 * item["comments"] + 4 * item["shares"] + item["views"] * 0.02
    eng = max(eng, 10)  # base so fresh news can still rank
    item["engagement"] = int(eng)
    item["velocity"] = round(eng / age, 2) if age else None
    return item


def _google_news() -> list[dict]:
    items: list[dict] = []
    for q in NEWS_QUERIES:
        url = (f"https://news.google.com/rss/search?q={quote(q + ' when:3d')}"
               f"&hl=en-US&gl=US&ceid=US:en")
        r = requests.get(url, headers={"User-Agent": UA}, timeout=TIMEOUT)
        r.raise_for_status()
        root = ET.fromstring(r.content)
        for it in root.findall(".//item")[:12]:
            title = (it.findtext("title") or "").strip()
            link = (it.findtext("link") or "").strip()
            if not link or not title:
                continue
            try:
                posted = parsedate_to_datetime(it.findtext("pubDate"))
            except Exception:
                posted = None
            src = it.find("{*}source")
            desc = (it.findtext("description") or "")[:600]
            items.append(_finalize(dict(
                url=link, title=title, text=desc, views=0, likes=0, comments=0, shares=0,
                creator=(src.text if src is not None else None), posted=posted.isoformat() if posted else None,
                platform="news", ageHours=_age_hours(posted))))
    return items


def _hacker_news() -> list[dict]:
    items: list[dict] = []
    since = int(datetime.now(timezone.utc).timestamp()) - 3 * 86400
    for q in HN_QUERIES:
        url = ("https://hn.algolia.com/api/v1/search_by_date"
               f"?query={quote(q)}&tags=story&numericFilters=created_at_i>{since},points>15&hitsPerPage=15")
        r = requests.get(url, headers={"User-Agent": UA}, timeout=TIMEOUT)
        r.raise_for_status()
        for h in r.json().get("hits", []):
            link = h.get("url") or f"https://news.ycombinator.com/item?id={h.get('objectID')}"
            title = h.get("title")
            if not title:
                continue
            posted = None
            if h.get("created_at_i"):
                posted = datetime.fromtimestamp(h["created_at_i"], tz=timezone.utc)
            items.append(_finalize(dict(
                url=link, title=title, text=(title or "")[:600], views=0,
                likes=int(h.get("points") or 0), comments=int(h.get("num_comments") or 0), shares=0,
                creator=h.get("author"), posted=posted.isoformat() if posted else None,
                platform="hackernews", ageHours=_age_hours(posted))))
    return items


def discover(force: bool = False) -> list[dict]:
    """Return normalized items from free sources. Reuses today's cache unless force=True."""
    if not force:
        cached = state.load_discovery_if_today()
        if cached:
            return cached

    items: list[dict] = []
    errors: list[str] = []
    for name, fn in (("news", _google_news), ("hackernews", _hacker_news)):
        try:
            items += fn()
        except Exception as e:
            errors.append(f"{name}: {e}")

    # Dedup by URL, keep the higher-engagement copy.
    best: dict[str, dict] = {}
    for it in items:
        k = it["url"]
        if k not in best or it["engagement"] > best[k]["engagement"]:
            best[k] = it
    items = list(best.values())

    if not items:
        raise RuntimeError("Discovery returned nothing. " + "; ".join(errors))
    if errors:
        print("[discovery] partial failures:", "; ".join(errors))
    state.save_discovery(items)
    return items
