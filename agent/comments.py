"""Comment pass: list -> classify -> draft replies (BOT_PROMPT 13-16). Selective by design."""
from __future__ import annotations

import json

from . import config, linkedin, llm, state

REPLY_CATEGORIES = {"question", "useful addition", "lead signal", "request for help", "objection", "positive reaction"}


def _text(c: dict) -> str:
    return ((c.get("message") or {}).get("text") or "").strip()


def classify_and_draft(post: dict, comments: list[dict]) -> list[dict]:
    if not comments:
        return []
    payload = [{"id": c.get("$URN") or c.get("id") or c.get("commentUrn"), "author": c.get("actor"), "text": _text(c)} for c in comments if _text(c)]
    system = llm.brand_context() + (
        "\n\nTASK: classify each comment (question, positive reaction, useful addition, objection, criticism, lead signal, "
        "request for help, spam, irrelevant) and draft a reply ONLY for meaningful ones, in priority order: questions, useful "
        "discussion, lead signals, thoughtful objections, meaningful positive comments. Replies: directly address the comment, "
        "use the commenter's context, concise, natural, add value, no generic praise ('Thanks for sharing!'), no aggressive selling, "
        "never fabricate facts or claim things not known. For lead signals do NOT pitch; ask about their situation. "
        "Vary wording across replies. Skip spam/irrelevant/criticism-that-is-just-abuse: reply=null."
    )
    user = (
        f"POST CAPTION:\n{post.get('caption','')[:1500]}\n\nCOMMENTS:\n{json.dumps(payload, ensure_ascii=False)}\n\n"
        'Return JSON: {"items":[{"id":str,"category":str,"reply":str|null}]}'
    )
    items = llm.complete_obj(system, user, max_tokens=2000, temperature=0.6).get("items", [])
    by_id = {p["id"]: p for p in payload}
    out = []
    for it in items:
        if it.get("reply") and it.get("category") in REPLY_CATEGORIES and it.get("id") in by_id:
            out.append({"postUrn": post["postUrn"], "commentUrn": it["id"], "author": by_id[it["id"]]["author"],
                        "category": it["category"], "reply": it["reply"], "original": by_id[it["id"]]["text"]})
    return out


def run_pass(days: int = 7) -> list[dict]:
    """Return drafted replies (not sent). Gracefully degrades if comment reads are not permitted."""
    drafted: list[dict] = []
    for post in state.recent_published(days):
        if not post.get("postUrn"):
            continue
        try:
            comments = linkedin.list_comments(post["postUrn"])
        except linkedin.LinkedInError as e:
            print(f"[comments] cannot read comments for {post['postUrn']}: {e}")
            continue
        replied = set(post.get("repliedTo", []))
        fresh = [c for c in comments if (c.get("$URN") or c.get("id")) not in replied]
        drafted += classify_and_draft(post, fresh)[: config.MAX_REPLIES_PER_POST_PER_RUN]
    return drafted


def send(replies: list[dict], publish: bool) -> list[dict]:
    results = []
    posts = state.published()
    for r in replies:
        res = linkedin.reply_comment(r["postUrn"], r["commentUrn"], r["reply"], publish=publish)
        results.append({**r, **res})
        if publish:
            for p in posts:
                if p.get("postUrn") == r["postUrn"]:
                    p.setdefault("repliedTo", []).append(r["commentUrn"])
    if publish:
        state._write(config.STATE / "published.json", posts)
    return results
