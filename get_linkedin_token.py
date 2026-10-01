#!/usr/bin/env python3
"""One-time LinkedIn OAuth helper.

Runs the 3-legged OAuth flow locally, exchanges the code for a member access
token, resolves your person URN via OpenID Connect, and writes both into .env.

Usage:
    python get_linkedin_token.py

Prerequisites (one time, in your LinkedIn app at developer.linkedin.com):
  1. Products: request/enable "Share on LinkedIn" (grants w_member_social) and
     "Sign In with LinkedIn using OpenID Connect" (grants openid, profile).
  2. Auth tab -> Authorized redirect URLs -> add EXACTLY:
         http://localhost:8000/callback
  3. LINKEDIN_CLIENT_ID / LINKEDIN_CLIENT_SECRET must be set in .env.
"""
from __future__ import annotations

import http.server
import os
import secrets
import threading
import urllib.parse
import webbrowser
from pathlib import Path

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
ENV_PATH = ROOT / ".env"
REDIRECT_URI = "http://localhost:8000/callback"
PORT = 8000
# openid+profile let us read the person id (sub); w_member_social lets us post.
SCOPES = "openid profile w_member_social"

load_dotenv(ENV_PATH)
CLIENT_ID = os.environ.get("LINKEDIN_CLIENT_ID", "").strip()
CLIENT_SECRET = os.environ.get("LINKEDIN_CLIENT_SECRET", "").strip()

_result: dict[str, str] = {}
_state = secrets.token_urlsafe(16)


class _Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        parts = urllib.parse.urlparse(self.path)
        if parts.path != "/callback":
            self.send_response(404)
            self.end_headers()
            return
        q = urllib.parse.parse_qs(parts.query)
        _result.update({k: v[0] for k, v in q.items()})
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        ok = "code" in _result and _result.get("state") == _state
        msg = "Authorization received. You can close this tab and return to the terminal." if ok \
            else f"Authorization failed: {_result.get('error_description', _result)}"
        self.wfile.write(f"<html><body style='font-family:sans-serif;padding:3rem'>{msg}</body></html>".encode())

    def log_message(self, *a):  # silence
        pass


def _upsert_env(key: str, value: str) -> None:
    lines = ENV_PATH.read_text().splitlines() if ENV_PATH.exists() else []
    out, found = [], False
    for ln in lines:
        if ln.strip().startswith(f"{key}="):
            out.append(f"{key}={value}")
            found = True
        else:
            out.append(ln)
    if not found:
        out.append(f"{key}={value}")
    ENV_PATH.write_text("\n".join(out) + "\n")


def main() -> int:
    if not CLIENT_ID or not CLIENT_SECRET:
        print("ERROR: set LINKEDIN_CLIENT_ID and LINKEDIN_CLIENT_SECRET in .env first.")
        return 1

    auth_url = "https://www.linkedin.com/oauth/v2/authorization?" + urllib.parse.urlencode({
        "response_type": "code",
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "state": _state,
        "scope": SCOPES,
    })

    server = http.server.HTTPServer(("localhost", PORT), _Handler)
    threading.Thread(target=server.handle_request, daemon=True).start()

    print("\nOpening your browser to authorize LinkedIn...")
    print("If it doesn't open, paste this URL:\n")
    print(auth_url, "\n")
    webbrowser.open(auth_url)

    # Block until the single callback request is handled.
    while "code" not in _result and "error" not in _result:
        import time
        time.sleep(0.3)

    if "error" in _result:
        print("Authorization failed:", _result.get("error_description", _result))
        return 1
    if _result.get("state") != _state:
        print("ERROR: state mismatch (possible CSRF); aborting.")
        return 1

    print("Exchanging code for access token...")
    tok = requests.post(
        "https://www.linkedin.com/oauth/v2/accessToken",
        data={
            "grant_type": "authorization_code",
            "code": _result["code"],
            "redirect_uri": REDIRECT_URI,
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=60,
    )
    if tok.status_code != 200:
        print("Token exchange failed:", tok.status_code, tok.text)
        return 1
    access_token = tok.json()["access_token"]
    expires_in = tok.json().get("expires_in")

    print("Resolving your person URN via /v2/userinfo...")
    ui = requests.get(
        "https://api.linkedin.com/v2/userinfo",
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=60,
    )
    if ui.status_code != 200:
        print("userinfo failed:", ui.status_code, ui.text)
        print("(The token still works for posting; set LINKEDIN_AUTHOR_URN manually.)")
        author_urn = ""
    else:
        sub = ui.json().get("sub", "")
        author_urn = f"urn:li:person:{sub}" if sub else ""
        print("  name:", ui.json().get("name"), " urn:", author_urn)

    _upsert_env("LINKEDIN_ACCESS_TOKEN", access_token)
    if author_urn:
        _upsert_env("LINKEDIN_AUTHOR_URN", author_urn)

    print("\nDone. Wrote LINKEDIN_ACCESS_TOKEN" + (" and LINKEDIN_AUTHOR_URN" if author_urn else "") + " to .env.")
    if expires_in:
        days = int(expires_in) // 86400
        print(f"Token valid ~{days} days. Re-run this script to refresh when it expires.")
    print("\nNext: python -m agent.cli status   then   python -m agent.cli run --lane post")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
