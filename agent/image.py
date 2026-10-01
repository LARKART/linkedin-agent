"""Image generation (NVIDIA FLUX by default, OpenAI optional) plus the section-10 vision quality gate."""
from __future__ import annotations

import base64
from pathlib import Path

import requests

from . import config, llm

STYLE_SUFFIX = (
    " Editorial photography or minimal graphic design, clean composition, strong contrast and hierarchy, "
    "restrained palette (deep navy, emerald green #50C878, a single small orange accent). "
    "No robots, no glowing brains, no circuit boards, no holograms, no neon, no dashboards, no stock-photo look. "
    "No text in the image."
)


class ImageError(RuntimeError):
    pass


def _nvidia(prompt: str, out: Path) -> Path:
    key = config.env("NVIDIA_API_KEY", required=True)
    url = config.env("NVIDIA_IMAGE_URL", "https://ai.api.nvidia.com/v1/genai/black-forest-labs/flux.1-dev")
    r = requests.post(
        url,
        headers={"Authorization": f"Bearer {key}", "Accept": "application/json"},
        json={"prompt": prompt, "width": 1344, "height": 768, "seed": 0, "steps": 30, "cfg_scale": 3.5},
        timeout=240,
    )
    r.raise_for_status()
    art = (r.json().get("artifacts") or [{}])[0]
    if art.get("finishReason") == "CONTENT_FILTERED":
        raise ImageError("CONTENT_FILTERED")
    b64 = art.get("base64")
    if not b64:
        raise ImageError("no image returned")
    data = base64.b64decode(b64)
    if len(data) < 5000:  # black placeholder guard
        raise ImageError("image looks like a blank placeholder")
    out.write_bytes(data)
    return out


def _openai(prompt: str, out: Path) -> Path:
    key = config.env("OPENAI_API_KEY", required=True)
    r = requests.post(
        "https://api.openai.com/v1/images/generations",
        headers={"Authorization": f"Bearer {key}"},
        json={"model": config.env("OPENAI_IMAGE_MODEL", "gpt-image-1"), "prompt": prompt, "size": "1536x1024"},
        timeout=240,
    )
    r.raise_for_status()
    b64 = r.json()["data"][0].get("b64_json")
    if not b64:
        raise ImageError("no image returned")
    out.write_bytes(base64.b64decode(b64))
    return out


def generate(prompt: str, filename: str) -> Path:
    provider = config.env("IMAGE_PROVIDER", "nvidia")
    out = config.IMAGES / f"{filename}.png"
    fn = _openai if provider == "openai" else _nvidia
    return fn(prompt + STYLE_SUFFIX, out)


def quality_gate(image: Path, post_idea: str) -> dict:
    system = (
        "You are a strict art director reviewing a LinkedIn post visual. Reject it if it looks obviously AI-generated, feels generic, "
        "does not communicate the post idea, has unnecessary elements, poor typography, clutter, resembles generic AI marketing "
        "imagery, or could accompany almost any AI post."
    )
    return llm.vision_json(
        system,
        f"POST IDEA: {post_idea}\nReturn JSON: {{\"pass\":bool,\"problems\":[str],\"betterPrompt\":str}}",
        image,
    )


def make_image(concept: str, post_idea: str, slug: str, date: str) -> tuple[Path | None, str, str]:
    """Return (path|None, final_prompt, status). Text-only beats a bad image (RUNBOOK 5)."""
    prompt = concept
    last_net_err = None
    for attempt in range(3):
        try:
            path = generate(prompt, f"{date}-{slug}-{attempt}")
        except ImageError as e:
            prompt = llm.complete(
                "Rewrite this image prompt to be safe and visually different while keeping the idea. One paragraph, prompt only.",
                f"FAILED WITH: {e}\nPROMPT: {prompt}", model=config.LLM_MODEL_FAST, max_tokens=300)
            continue
        except requests.exceptions.RequestException as e:
            # Transient network/timeout from the image provider: retry with the same prompt.
            last_net_err = e
            continue
        except Exception as e:
            return None, prompt, f"generation error: {e}"
        verdict = quality_gate(path, post_idea)
        if verdict.get("pass"):
            return path, prompt, "generated, gate passed"
        prompt = verdict.get("betterPrompt") or prompt
    if last_net_err is not None:
        return None, prompt, f"text-only (image provider unreachable after retries: {last_net_err})"
    return None, prompt, "text-only (image failed generation or quality gate)"
