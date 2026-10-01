"""Approval notifications. Always logs to disk first; optionally pings a webhook (Slack/Discord/Telegram-compatible)."""
from __future__ import annotations

import requests

from . import config


def send(title: str, message: str) -> bool:
    print(f"\n=== {title} ===\n{message}\n")
    url = config.env("NOTIFY_WEBHOOK_URL")
    if not url:
        return False
    try:
        # Slack-style payload; Discord accepts "content" so send both.
        r = requests.post(url, json={"text": f"*{title}*\n{message}", "content": f"**{title}**\n{message}"[:1900]}, timeout=20)
        return r.ok
    except Exception as e:
        print(f"[notify] webhook failed: {e}")
        return False
