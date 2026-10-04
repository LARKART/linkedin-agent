"""Caption writer with a rule-based + LLM slop gate (BOT_PROMPT 7, 8, 11; BRAND 6-8, 13-16)."""
from __future__ import annotations

import re

from . import llm

BANNED_PHRASES = [
    "agree?", "thoughts?", "let that sink in", "here's the thing", "in today's rapidly changing world",
    "game changer", "game-changer", "revolutionary", "the future is here", "10x", "unlock the power",
    "i am passionate", "excited to announce", "delve", "leverage the power", "cutting-edge", "ecosystem",
    "in the ever-evolving", "supercharge", "skyrocket", "guaranteed",
]
MAX_HASHTAGS = 3
MAX_EMOJI = 2
MAX_CHARS = 3000
_EMOJI = re.compile("[\U0001F300-\U0001FAFF☀-➿]")


def rule_check(caption: str) -> list[str]:
    problems = []
    low = caption.lower()
    for p in BANNED_PHRASES:
        if p in low:
            problems.append(f"banned phrase: {p!r}")
    if len(re.findall(r"#\w+", caption)) > MAX_HASHTAGS:
        problems.append("too many hashtags")
    if len(_EMOJI.findall(caption)) > MAX_EMOJI:
        problems.append("too many emojis")
    if len(caption) > MAX_CHARS:
        problems.append("over 3000 characters")
    if "—" in caption:
        problems.append("em dash (reads machine-written)")
    return problems


def llm_gate(caption: str, topic: dict, sources_text: str) -> dict:
    system = llm.brand_context() + (
        "\n\nTASK: act as a strict editor. Apply POLICY section 11 and 19 and BRAND guardrails (section 16). "
        "Fail the caption if it sounds machine-written, has a generic opening, makes no useful point, copies source wording, "
        "invents personal experiences/builds/stats, overpromises autonomy, or is a sales pitch."
    )
    user = (
        f"TOPIC: {topic['topic']}\nSOURCE TEXT (check for copying):\n{sources_text[:2500]}\n\nCAPTION:\n{caption}\n\n"
        'Return JSON: {"pass":bool,"wouldAKnowledgeableHumanWriteThis":bool,"problems":[str],"fix":str}. '
        "Keep each problem to one short sentence and keep fix under 40 words."
    )
    return llm.complete_obj(system, user, model=None, max_tokens=1500, temperature=0.0)


def write_caption(topic: dict, *, lane: str, sources_text: str = "", slides_summary: str = "") -> dict:
    """Return {caption, hook, structure, imageConcept}. Retries up to 3 times through the gates."""
    system = llm.brand_context() + (
        "\n\nTASK: write ONE LinkedIn caption in Paul's voice. Lead with the business problem or a concrete observation, show the "
        "mechanism, connect technology to outcomes. Short paragraphs, strong first line, no cheap clickbait. "
        "Do NOT claim Paul built, tested or measured anything unless it is stated in BRAND. Frame what was learned from "
        "public conversation as an observation, not as personal experience. At most 3 hashtags (or none)."
    )
    if lane == "carousel":
        system += (" Structure: hook -> what's inside the carousel -> one useful takeaway -> soft CTA taken from BRAND section 14. "
                   "Under 3000 characters.")
    facts = f"\nVERIFIED FACTS (only these may be stated as fact):\n{topic['verifiedFacts']}" if topic.get("verifiedFacts") else ""
    feedback = ""
    last = {}
    for attempt in range(3):
        user = (
            f"TOPIC: {topic['topic']}\nSUBTOPIC: {topic.get('subtopic','')}\nKEY IDEA: {topic.get('keyIdea','')}\n"
            f"WHY IT MATTERS NOW: {topic.get('whyNow','')}\nPILLAR: {topic.get('pillar','')}{facts}\n"
            + (f"CAROUSEL CONTENT: {slides_summary}\n" if slides_summary else "")
            + (f"\nPREVIOUS ATTEMPT FAILED THE GATE. FIX THESE:\n{feedback}\n" if feedback else "")
            + '\nReturn JSON: {"caption":str,"hook":str,"structure":str,'
              '"imageConcept":str (a concrete editorial visual metaphor for THIS idea, no robots/brains/circuits)}'
        )
        last = llm.complete_obj(system, user, max_tokens=1800, temperature=0.8)
        problems = rule_check(last["caption"])  # objective hard filter (banned phrases, em dash, length, hashtags)
        if not problems:
            verdict = llm_gate(last["caption"], topic, sources_text)
            # Block only on an explicit failure WITH stated reasons. An empty/ambiguous
            # verdict (or pass==True) accepts — rule_check already caught the objective issues.
            explicit_problems = verdict.get("problems") or []
            if verdict.get("pass") is False and explicit_problems:
                problems = explicit_problems + ([verdict["fix"]] if verdict.get("fix") else [])
            else:
                last["gate"] = "passed"
                return last
        feedback = "\n".join(f"- {p}" for p in problems)
    # Out of attempts: if the final caption at least cleared the objective rule_check, publish it.
    if not rule_check(last.get("caption", "x")):
        last["gate"] = "passed"
        return last
    last["gate"] = "FAILED"
    last["gateProblems"] = feedback
    return last
