"""Daily pipelines: 'post' (1 PM single image) and 'carousel' (8 PM educational PDF). Policy: docs/BOT_PROMPT.md."""
from __future__ import annotations

import re
from pathlib import Path

from . import carousel, comments, config, discovery, image, linkedin, notify, selector, state, video, writer


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:40] or "post"


def _sources_text(topic: dict, items: list[dict]) -> str:
    urls = {s["url"] for s in topic.get("sources", [])}
    return "\n".join((i.get("title") or "") + " " + (i.get("text") or "") for i in items if i["url"] in urls)


def _publish_draft(draft: dict) -> dict:
    res = linkedin.create_post(
        draft["caption"],
        image=Path(draft["imagePath"]) if draft.get("imagePath") else None,
        document=Path(draft["documentPath"]) if draft.get("documentPath") else None,
        video=Path(draft["videoPath"]) if draft.get("videoPath") else None,
        title=draft.get("title", draft["topic"]), publish=True)
    record = {
        "date": draft["date"], "publishedAt": state.now().isoformat(), "postUrn": res["postUrn"], "lane": draft["lane"],
        "topic": draft["topic"], "subtopic": draft.get("subtopic"), "hook": draft.get("hook"), "caption": draft["caption"],
        "imagePrompt": draft.get("imagePrompt"), "imagePath": draft.get("imagePath"),
        "documentPath": draft.get("documentPath"), "videoPath": draft.get("videoPath"),
        "videoStyle": draft.get("videoStyle"), "sources": draft.get("sources", []), "status": "published",
    }
    state.add_published(record)
    state.add_topic(draft["topic"], draft.get("hook", ""), draft.get("imageConcept", ""), draft.get("structure", ""))
    return record


def run(lane: str, *, force_discovery: bool = False) -> dict | None:
    """lane: 'post' | 'carousel'. Returns the draft/record, or None if nothing viable."""
    m = config.mode()
    date = state.now().date().isoformat()
    notes: list[str] = []

    # Hard rule: max one new post per day per lane (carousel is its own lane per RUNBOOK).
    if any(r.get("date") == date and r.get("lane") == lane for r in state.published()):
        print(f"[{lane}] already published today; stopping.")
        return None

    # 1. comment pass first so replies land within 24h
    replies: list[dict] = []
    try:
        replies = comments.run_pass()
        if replies and m == "auto":
            comments.send(replies, publish=True)
            replies = []
    except Exception as e:
        notes.append(f"comment pass failed: {e}")

    # 2-3b. discovery, selection, security verification
    items = discovery.discover(force=force_discovery)
    topic, sel_notes = selector.select(items, "carousel" if lane == "carousel" else "post")
    notes += sel_notes
    if not topic:
        notify.send(f"LinkedIn {lane}: nothing published", "No viable topic after dedup/verification.\n" + "\n".join(notes))
        return None

    # 4-5. content
    src_text = _sources_text(topic, items)
    draft = {"date": date, "lane": lane, "status": "staged", "topic": topic["topic"], "subtopic": topic.get("subtopic"),
             "whyNow": topic.get("whyNow"), "sources": topic.get("sources", []), "replies": replies, "notes": notes}

    if lane == "carousel":
        spec = carousel.make_spec(topic)
        out_dir = config.CAROUSELS / date
        pdf, pngs = carousel.render(spec, out_dir)
        review = carousel.review(pngs, topic["topic"])
        if not review["pass"]:  # regenerate once
            spec = carousel.make_spec(topic)
            pdf, pngs = carousel.render(spec, out_dir)
            review = carousel.review(pngs, topic["topic"])
        summary = "; ".join(s["headline"] for s in spec["slides"])
        cap = writer.write_caption(topic, lane="carousel", sources_text=src_text, slides_summary=summary)
        draft.update(documentPath=str(pdf), title=spec.get("title", topic["topic"]), slideReview=review)
    else:
        cap = writer.write_caption(topic, lane="post", sources_text=src_text)

    draft.update(caption=cap["caption"], hook=cap.get("hook"), structure=cap.get("structure"),
                 imageConcept=cap.get("imageConcept"), gate=cap["gate"])

    if cap["gate"] != "passed":
        draft["status"] = "blocked"
        state.save_draft(lane, draft)
        notify.send(f"LinkedIn {lane}: blocked by quality gate", cap.get("gateProblems", ""))
        return draft

    if lane == "post":
        path, prompt, status = image.make_image(cap.get("imageConcept", topic["topic"]), topic["topic"], _slug(topic["topic"]), date)
        draft.update(imagePath=str(path) if path else None, imagePrompt=prompt, imageStatus=status)
        # A post must have an image. If generation failed, do not publish text-only.
        if not path and config.env("REQUIRE_IMAGE", "true").lower() != "false":
            draft["status"] = "blocked"
            draft["gate"] = "blocked-no-image"
            state.save_draft(lane, draft)
            notify.send("LinkedIn post: skipped (no image)",
                        f"Topic: {topic['topic']}\nImage step: {status}\nNothing published (a post requires an image).")
            return draft

    if lane == "video":
        n_videos = sum(1 for r in state.published() if r.get("lane") == "video")
        vstyle = video.pick_style(n_videos)
        vpath, vstatus, vstyle = video.make_video(topic, vstyle, _slug(topic["topic"]), date)
        draft.update(videoPath=str(vpath) if vpath else None, videoStatus=vstatus, videoStyle=vstyle)
        if not vpath:
            draft["status"] = "blocked"
            draft["gate"] = "blocked-no-video"
            state.save_draft(lane, draft)
            notify.send("LinkedIn video: skipped (no video)",
                        f"Topic: {topic['topic']}\nVideo step: {vstatus}\nNothing published (a video post requires a video).")
            return draft

    if lane == "slidevideo":
        vpath, vstatus, vstyle = video.make_slide_video(topic, _slug(topic["topic"]), date)
        draft.update(videoPath=str(vpath) if vpath else None, videoStatus=vstatus, videoStyle=vstyle)
        if not vpath:
            draft["status"] = "blocked"
            draft["gate"] = "blocked-no-video"
            state.save_draft(lane, draft)
            notify.send("LinkedIn slide-video: skipped (no video)",
                        f"Topic: {topic['topic']}\nVideo step: {vstatus}\nNothing published (requires a video).")
            return draft

    # 6/7. approve vs auto
    if m == "approve":
        state.save_draft(lane, draft)
        notify.send(
            f"LinkedIn {lane} ready - approval needed",
            f"{draft['hook']}\n\n{draft['caption']}\n\nImage/PDF: {draft.get('imagePath') or draft.get('documentPath') or 'text-only'}\n"
            f"Sources: {', '.join(s['url'] for s in draft['sources'])}\n"
            + ("\nDrafted replies:\n" + "\n".join(f"- {r['reply']}" for r in replies) if replies else "")
            + f"\n\nRun: python -m agent.cli approve --lane {lane}   (or: skip --lane {lane})")
        return draft

    record = _publish_draft(draft)
    state.save_draft(lane, {**draft, "status": "published", "postUrn": record["postUrn"]})
    notify.send(
        "LinkedIn post published",
        f"Topic: {draft['topic']}\nWhy now: {draft['whyNow']}\nPlatforms: {', '.join({s['platform'] for s in draft['sources']})}\n"
        f"Post: {record['postUrn']} at {record['publishedAt']}\nImage: {draft.get('imageStatus','n/a')}\nQuality gates: passed\n"
        + "\n".join(notes))
    return record


def approve(lane: str, date: str | None = None) -> dict:
    d = state.load_draft(lane, date)
    if not d or d["status"] != "staged":
        raise RuntimeError("No staged draft to approve.")
    if any(r.get("date") == d["date"] and r.get("lane") == lane for r in state.published()):
        raise RuntimeError("Already published for that day/lane.")
    record = _publish_draft(d)
    if d.get("replies"):
        comments.send(d["replies"], publish=True)
    d.update(status="published", postUrn=record["postUrn"])
    state.save_draft(lane, d)
    return record


def skip(lane: str, date: str | None = None) -> None:
    d = state.load_draft(lane, date)
    if d:
        d["status"] = "discarded"
        state.save_draft(lane, d)
