"""Notifications. Always logs to disk first; optionally pings a webhook and/or emails via Gmail SMTP."""
from __future__ import annotations

import smtplib
import ssl
from email.message import EmailMessage

import requests

from . import config


def _webhook(title: str, message: str) -> bool:
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


def _resend(title: str, message: str) -> bool:
    """Send email over HTTPS via Resend (works from CI where SMTP is blocked).
    Needs RESEND_API_KEY and NOTIFY_EMAIL_TO. Sender defaults to Resend's test domain."""
    key = config.env("RESEND_API_KEY")
    to = config.env("NOTIFY_EMAIL_TO")
    if not key or not to:
        return False
    sender = config.env("RESEND_FROM", "LinkedIn Agent <onboarding@resend.dev>")
    try:
        r = requests.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={"from": sender, "to": [to], "subject": f"[LinkedIn agent] {title}", "text": message},
            timeout=20,
        )
        if r.ok:
            return True
        print(f"[notify] resend failed: {r.status_code} {r.text[:200]}")
        return False
    except Exception as e:
        print(f"[notify] resend failed: {e}")
        return False


def _email(title: str, message: str) -> bool:
    """Send via Gmail SMTP. Needs GMAIL_ADDRESS + GMAIL_APP_PASSWORD (a Google App Password,
    not the account password). NOTIFY_EMAIL_TO defaults to the sender address."""
    sender = config.env("GMAIL_ADDRESS")
    app_pw = config.env("GMAIL_APP_PASSWORD")
    if not sender or not app_pw:
        return False
    to = config.env("NOTIFY_EMAIL_TO", sender)
    msg = EmailMessage()
    msg["Subject"] = f"[LinkedIn agent] {title}"
    msg["From"] = sender
    msg["To"] = to
    msg.set_content(message)
    pw = app_pw.replace(" ", "")  # app passwords are shown with spaces
    ctx = ssl.create_default_context()
    # 465 implicit SSL first (reliable on GitHub runners); fall back to 587 STARTTLS.
    errors = []
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=30, context=ctx) as s:
            s.login(sender, pw)
            s.send_message(msg)
        return True
    except Exception as e:
        errors.append(f"465: {e}")
    try:
        with smtplib.SMTP("smtp.gmail.com", 587, timeout=30) as s:
            s.ehlo()
            s.starttls(context=ctx)
            s.login(sender, pw)
            s.send_message(msg)
        return True
    except Exception as e:
        errors.append(f"587: {e}")
    print(f"[notify] email failed: {' | '.join(errors)}")
    return False


def send(title: str, message: str) -> bool:
    print(f"\n=== {title} ===\n{message}\n")
    # Fire all configured channels; return True if any delivered.
    # Resend (HTTPS) is preferred for CI; SMTP email works from a normal network (e.g. local Mac).
    results = [_webhook(title, message), _resend(title, message), _email(title, message)]
    return any(results)
