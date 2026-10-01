"""Cluster -> score -> dedup -> select, plus the security-story verification lane (RUNBOOK 3b)."""
from __future__ import annotations

import json

from . import llm, state

SECURITY_WORDS = ("breach", "attack", "exploit", "leak", "hack", "malware", "credential", "ransomware", "vulnerab", "compromised")


def _compact(items: list[dict], limit: int = 45) -> list[dict]:
    ranked = sorted(items, key=lambda i: (i.get("velocity") or 0), reverse=True)[:limit]
    return [
        {"id": n, "platform": i["platform"], "url": i["url"], "ageHours": i.get("ageHours"),
         "velocity": i.get("velocity"), "views": i["views"], "likes": i["likes"], "comments": i["comments"],
         "text": (i.get("title") or "") + " | " + (i.get("text") or "")[:400]}
        for n, i in enumerate(ranked)
    ], ranked


def rank_topics(items: list[dict], lane: str) -> list[dict]:
    compact, ranked = _compact(items)
    recent = [t["topic"] for t in state.topics()]
    system = llm.brand_context() + (
        "\n\nTASK: cluster the sources into underlying ideas/topics and score each (0-100) using POLICY section 4 weights "
        "(freshness 25, engagement velocity 20, relevance 20, novelty 15, discussion potential 10, practical usefulness 10). "
        "Prefer velocity over lifetime views. Each topic MUST fit a BRAND content pillar (section 7); drop those that cannot. "
        "Skip anything too close to RECENT TOPICS. Identify the underlying idea, never copy source wording."
    )
    if lane == "carousel":
        system += " For the carousel lane, favor ideas that can be TAUGHT (mechanism, steps, lessons)."
    user = (
        f"RECENT TOPICS (do not repeat): {json.dumps(recent)}\n\nSOURCES:\n{json.dumps(compact, ensure_ascii=False)}\n\n"
        'Return JSON: {"topics":[{"topic":str,"subtopic":str,"keyIdea":str,"whyNow":str,"pillar":str,'
        '"score":number,"sourceIds":[int],"isSecurityIncident":bool}]} sorted by score desc, max 6.'
    )
    out = llm.complete_json(system, user, max_tokens=2500, temperature=0.3)
    topics = out.get("topics", [])
    for t in topics:
        t["sources"] = [
            {"platform": ranked[i]["platform"], "url": ranked[i]["url"], "velocity": ranked[i].get("velocity")}
            for i in t.get("sourceIds", []) if 0 <= i < len(ranked)
        ]
        if any(w in (t.get("topic", "") + t.get("keyIdea", "")).lower() for w in SECURITY_WORDS):
            t["isSecurityIncident"] = True
    return topics


def verify_security_story(topic: dict) -> tuple[bool, str, str]:
    """Return (verified, confirmed_facts, note). Needs >= 2 independent corroborating sources."""
    q = (
        f"Verify this reported security story with independent sources (vendor statement, official blog, reputable news, "
        f"regulator/CERT). Story: {topic['topic']} - {topic.get('keyIdea','')}\n\n"
        "Search several distinct queries. Then answer in this exact format:\n"
        "VERIFIED: yes|no\nSOURCES: <at least two independent URLs or outlet names, not the viral post>\n"
        "CONFIRMED FACTS: <only what the sources confirm>\nUNKNOWN: <what is still unconfirmed>\n"
        "If fewer than two independent sources confirm it, answer VERIFIED: no."
    )
    try:
        ans = llm.web_search_answer(q, max_uses=6)
    except Exception as e:
        return False, "", f"verification search failed: {e}"
    ok = "verified: yes" in ans.lower()
    return ok, ans, "" if ok else "could not corroborate with independent sources"


def select(items: list[dict], lane: str) -> tuple[dict | None, list[str]]:
    """Return (chosen_topic_or_None, notes). Notes carry SKIPPED lines for the notification."""
    notes: list[str] = []
    for t in rank_topics(items, lane):
        if t.get("isSecurityIncident"):
            ok, facts, why = verify_security_story(t)
            if not ok:
                notes.append(f"SKIPPED (unverified security story): {t['topic']} - {why or 'could not corroborate with independent sources'}")
                continue
            t["verifiedFacts"] = facts
        return t, notes
    return None, notes
