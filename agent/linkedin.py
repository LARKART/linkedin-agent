"""Official LinkedIn REST API client (Posts, Images, Documents, socialActions comments).

Notes:
- Posting needs w_member_social. READING comments needs r_member_social (restricted product, approval required).
- If comment reads are not permitted for your app, comments.py degrades gracefully (see README).
- dry_run is the default; only publish=True sends.
"""
from __future__ import annotations

from pathlib import Path
from urllib.parse import quote

import requests

from . import config

BASE = "https://api.linkedin.com/rest"


class LinkedInError(RuntimeError):
    pass


def _headers(extra: dict | None = None) -> dict:
    h = {
        "Authorization": f"Bearer {config.env('LINKEDIN_ACCESS_TOKEN', required=True)}",
        "LinkedIn-Version": config.LINKEDIN_API_VERSION,
        "X-Restli-Protocol-Version": "2.0.0",
    }
    h.update(extra or {})
    return h


def _check(r: requests.Response) -> requests.Response:
    if not r.ok:
        raise LinkedInError(f"{r.request.method} {r.url} -> {r.status_code}: {r.text[:400]}")
    return r


def author_urn() -> str:
    urn = config.env("LINKEDIN_AUTHOR_URN", required=True)  # urn:li:person:XXXX or urn:li:organization:XXXX
    return urn


def _upload(kind: str, path: Path) -> str:
    """kind: 'images' or 'documents'. Returns the asset URN."""
    init = _check(requests.post(
        f"{BASE}/{kind}?action=initializeUpload",
        headers=_headers({"Content-Type": "application/json"}),
        json={"initializeUploadRequest": {"owner": author_urn()}}, timeout=60)).json()["value"]
    with open(path, "rb") as f:
        _check(requests.put(init["uploadUrl"], data=f.read(),
                            headers={"Authorization": f"Bearer {config.env('LINKEDIN_ACCESS_TOKEN')}"}, timeout=180))
    return init["image"] if kind == "images" else init["document"]


def create_post(text: str, *, image: Path | None = None, document: Path | None = None,
                title: str = "", publish: bool = False) -> dict:
    if image and document:
        raise ValueError("Never pass both image and document")
    body = {
        "author": author_urn(),
        "commentary": text,
        "visibility": "PUBLIC",
        "distribution": {"feedDistribution": "MAIN_FEED", "targetEntities": [], "thirdPartyDistributionChannels": []},
        "lifecycleState": "PUBLISHED",
        "isReshareDisabledByAuthor": False,
    }
    if not publish:
        return {"dryRun": True, "body": body, "image": str(image) if image else None,
                "document": str(document) if document else None}
    if image:
        body["content"] = {"media": {"id": _upload("images", image), "altText": (title or "Post visual")[:120]}}
    elif document:
        body["content"] = {"media": {"id": _upload("documents", document), "title": (title or "Carousel")[:100]}}
    r = _check(requests.post(f"{BASE}/posts", headers=_headers({"Content-Type": "application/json"}), json=body, timeout=60))
    return {"dryRun": False, "postUrn": r.headers.get("x-restli-id") or r.headers.get("x-linkedin-id")}


def list_comments(post_urn: str, count: int = 50) -> list[dict]:
    r = _check(requests.get(f"{BASE}/socialActions/{quote(post_urn, safe='')}/comments",
                            headers=_headers(), params={"count": count}, timeout=60))
    return r.json().get("elements", [])


def reply_comment(post_urn: str, parent_comment_urn: str, text: str, *, publish: bool = False) -> dict:
    body = {"actor": author_urn(), "object": post_urn, "parentComment": parent_comment_urn, "message": {"text": text}}
    if not publish:
        return {"dryRun": True, "body": body}
    r = _check(requests.post(f"{BASE}/socialActions/{quote(post_urn, safe='')}/comments",
                             headers=_headers({"Content-Type": "application/json"}), json=body, timeout=60))
    return {"dryRun": False, "commentUrn": r.headers.get("x-restli-id")}
