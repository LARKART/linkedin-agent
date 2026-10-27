"""Thin Anthropic wrapper with JSON helpers, brand context, and optional web search."""
from __future__ import annotations

import base64
import json
import re
from pathlib import Path

from . import config

_client = None


def client():
    global _client
    if _client is None:
        import anthropic

        _client = anthropic.Anthropic(api_key=config.env("ANTHROPIC_API_KEY", required=True))
    return _client


def _text(resp) -> str:
    return "".join(b.text for b in resp.content if getattr(b, "type", "") == "text").strip()


def _nvidia_chat(system: str, user: str, max_tokens: int, temperature: float) -> str:
    """Free fallback LLM: NVIDIA NIM (OpenAI-compatible). Uses NVIDIA_CHAT_API_KEY or NVIDIA_API_KEY."""
    import requests
    key = config.env("NVIDIA_CHAT_API_KEY") or config.env("NVIDIA_API_KEY", required=True)
    url = config.env("NVIDIA_CHAT_URL", "https://integrate.api.nvidia.com/v1/chat/completions")
    model = config.env("NVIDIA_CHAT_MODEL", "z-ai/glm-5.3-flash")
    import json as _json
    # Stream (reasoning models hang on non-stream); accumulate content deltas.
    r = requests.post(url, headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                      json={"model": model, "max_tokens": max_tokens, "temperature": temperature, "stream": True,
                            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]},
                      timeout=(10, 120), stream=True)
    r.raise_for_status()
    parts, reasoning = [], []
    for line in r.iter_lines(decode_unicode=True):
        if not line or not line.startswith("data:"):
            continue
        payload = line[5:].strip()
        if payload == "[DONE]":
            break
        try:
            delta = _json.loads(payload)["choices"][0]["delta"]
        except Exception:
            continue
        if delta.get("content"):
            parts.append(delta["content"])
        elif delta.get("reasoning_content"):
            reasoning.append(delta["reasoning_content"])
    return ("".join(parts) or "".join(reasoning)).strip()


def complete(system: str, user: str, *, model: str | None = None, max_tokens: int = 2000, temperature: float = 0.7) -> str:
    # Primary: Anthropic. Fallback: free NVIDIA NIM when Anthropic fails (e.g. out of credits).
    try:
        resp = client().messages.create(
            model=model or config.LLM_MODEL,
            max_tokens=max_tokens,
            thinking={"type": "disabled"},
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        text = _text(resp)
        if text:
            return text
        raise RuntimeError("empty Anthropic response")
    except Exception as e:
        print(f"[llm] Anthropic failed ({str(e)[:120]}); falling back to NVIDIA")
        return _nvidia_chat(system, user, max_tokens, temperature)


def _extract_json(text: str):
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if fence:
        text = fence.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"(\{.*\}|\[.*\])", text, re.S)
        if m:
            return json.loads(m.group(1))
        raise


def complete_json(system: str, user: str, **kw):
    system = system + "\n\nReturn ONLY valid JSON. No prose, no markdown fences. Escape quotes and newlines inside strings."
    last_err = None
    for attempt in range(3):
        raw = complete(system, user, **kw)
        try:
            return _extract_json(raw)
        except (json.JSONDecodeError, ValueError) as e:
            last_err = e
            # Nudge the model to emit strictly valid JSON on the next attempt.
            user = user + "\n\nYour previous reply was not valid JSON and could not be parsed. Return ONLY a single valid JSON value, nothing else."
    raise last_err


def _as_obj(out):
    """Models sometimes wrap the requested object in a single-element array; unwrap it."""
    if isinstance(out, list) and len(out) == 1 and isinstance(out[0], dict):
        return out[0]
    return out


def complete_obj(system: str, user: str, **kw) -> dict:
    return _as_obj(complete_json(system, user, **kw))


def vision_json(system: str, user: str, image_path: Path, **kw):
    # Vision needs Anthropic; when it's unavailable (fallback mode), pass permissively so the
    # pipeline keeps shipping. Quality gates become advisory rather than blocking.
    try:
        client().messages.create(model=config.LLM_MODEL, max_tokens=4,
                                 thinking={"type": "disabled"}, messages=[{"role": "user", "content": "ok"}])
    except Exception as e:
        print(f"[llm] vision unavailable ({str(e)[:100]}); gate passes by default")
        return {"pass": True, "problems": [], "betterPrompt": ""}
    raw = Path(image_path).read_bytes()
    data = base64.standard_b64encode(raw).decode()
    # Sniff the real format from magic bytes; generators often save JPEG under a .png name.
    if raw[:3] == b"\xff\xd8\xff":
        media = "image/jpeg"
    elif raw[:8] == b"\x89PNG\r\n\x1a\n":
        media = "image/png"
    elif raw[:4] == b"RIFF" and raw[8:12] == b"WEBP":
        media = "image/webp"
    elif raw[:6] in (b"GIF87a", b"GIF89a"):
        media = "image/gif"
    else:
        ext = Path(image_path).suffix.lower().lstrip(".")
        media = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png", "webp": "image/webp"}.get(ext, "image/png")
    prompt = user
    last_err = None
    for attempt in range(3):
        resp = client().messages.create(
            model=kw.get("model") or config.LLM_MODEL,
            max_tokens=kw.get("max_tokens", 800),
            thinking={"type": "disabled"},
            system=system + "\n\nReturn ONLY valid JSON.",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "image", "source": {"type": "base64", "media_type": media, "data": data}},
                        {"type": "text", "text": prompt},
                    ],
                }
            ],
        )
        try:
            return _as_obj(_extract_json(_text(resp)))
        except (json.JSONDecodeError, ValueError) as e:
            last_err = e
            prompt = user + "\n\nYour previous reply was not valid JSON. Return ONLY a single valid JSON object, nothing else."
    raise last_err


def web_search_answer(question: str, max_uses: int = 5) -> str:
    """Use Anthropic's server-side web search tool. Raises on failure so callers can treat as 'unverified'."""
    resp = client().messages.create(
        model=config.LLM_MODEL,
        max_tokens=2000,
        thinking={"type": "disabled"},
        tools=[{"type": "web_search_20250305", "name": "web_search", "max_uses": max_uses}],
        messages=[{"role": "user", "content": question}],
    )
    return _text(resp)


_BRAND_CACHE = None


def brand_context() -> str:
    """BRAND.md wins over BOT_PROMPT on style conflicts (per RUNBOOK §4)."""
    global _BRAND_CACHE
    if _BRAND_CACHE is None:
        brand = (config.DOCS / "BRAND.md").read_text()
        policy = (config.DOCS / "BOT_PROMPT.md").read_text()
        _BRAND_CACHE = (
            "You write LinkedIn content for Paul Charles (Lark AI Agency).\n"
            "PRECEDENCE: where BRAND and POLICY disagree on voice or style, BRAND wins.\n"
            "Never invent builds, anecdotes, statistics, results, or personal experiences. "
            "First-person claims must be limited to what BRAND says Paul genuinely does.\n\n"
            f"=== BRAND ===\n{brand}\n\n=== POLICY (content rules, sections 5-11) ===\n{policy}"
        )
    return _BRAND_CACHE
