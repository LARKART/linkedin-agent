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


def _upload_video(path: Path) -> str:
    """Chunked video upload per the LinkedIn Videos API. Returns the video URN."""
    size = Path(path).stat().st_size
    init = _check(requests.post(
        f"{BASE}/videos?action=initializeUpload",
        headers=_headers({"Content-Type": "application/json"}),
        json={"initializeUploadRequest": {"owner": author_urn(), "fileSizeBytes": size,
                                           "uploadCaptions": False, "uploadThumbnail": False}},
        timeout=60)).json()["value"]
    video_urn = init["video"]
    token = init.get("uploadToken", "")
    etags = []
    with open(path, "rb") as f:
        for instr in init["uploadInstructions"]:
            first, last = instr["firstByte"], instr["lastByte"]
            f.seek(first)
            chunk = f.read(last - first + 1)
            r = _check(requests.put(instr["uploadUrl"], data=chunk,
                                    headers={"Authorization": f"Bearer {config.env('LINKEDIN_ACCESS_TOKEN')}",
                                             "Content-Type": "application/octet-stream"}, timeout=300))
            etags.append(r.headers.get("etag") or r.headers.get("ETag"))
    _check(requests.post(
        f"{BASE}/videos?action=finalizeUpload",
        headers=_headers({"Content-Type": "application/json"}),
        json={"finalizeUploadRequest": {"video": video_urn, "uploadToken": token, "uploadedPartIds": etags}},
        timeout=60))
    return video_urn


def create_post(text: str, *, image: Path | None = None, document: Path | None = None,
                video: Path | None = None, title: str = "", publish: bool = False) -> dict:
    if sum(x is not None for x in (image, document, video)) > 1:
        raise ValueError("Pass at most one of image/document/video")
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
                "document": str(document) if document else None, "video": str(video) if video else None}
    if image:
        body["content"] = {"media": {"id": _upload("images", image), "altText": (title or "Post visual")[:120]}}
    elif document:
        body["content"] = {"media": {"id": _upload("documents", document), "title": (title or "Carousel")[:100]}}
    elif video:
        body["content"] = {"media": {"id": _upload_video(video), "title": (title or "Video")[:100]}}
    r = _check(requests.post(f"{BASE}/posts", headers=_headers({"Content-Type": "application/json"}), json=body, timeout=60))
    return {"dryRun": False, "postUrn": r.headers.get("x-restli-id") or r.headers.get("x-linkedin-id")}


def list_comments(post_urn: str, count: int = 50) -> list[dict]:
    r = _check(requests.get(f"{BASE}/socialActions/{quote(post_urn, safe='')}/comments",
                            headers=_headers(), params={"count": count}, timeout=60))
    return r.json().get("elements", [])


def comment_on_post(post_urn: str, text: str, *, publish: bool = False) -> dict:
    """Top-level comment on a post (e.g. the author's own first comment). Needs w_member_social."""
    body = {"actor": author_urn(), "object": post_urn, "message": {"text": text}}
    if not publish:
        return {"dryRun": True, "body": body}
    r = _check(requests.post(f"{BASE}/socialActions/{quote(post_urn, safe='')}/comments",
                             headers=_headers({"Content-Type": "application/json"}), json=body, timeout=60))
    return {"dryRun": False, "commentUrn": r.headers.get("x-restli-id")}


def reply_comment(post_urn: str, parent_comment_urn: str, text: str, *, publish: bool = False) -> dict:
    body = {"actor": author_urn(), "object": post_urn, "parentComment": parent_comment_urn, "message": {"text": text}}
    if not publish:
        return {"dryRun": True, "body": body}
    r = _check(requests.post(f"{BASE}/socialActions/{quote(post_urn, safe='')}/comments",
                             headers=_headers({"Content-Type": "application/json"}), json=body, timeout=60))
    return {"dryRun": False, "commentUrn": r.headers.get("x-restli-id")}
