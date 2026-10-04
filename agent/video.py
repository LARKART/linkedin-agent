"""Branded video lane. Builds an MP4 from branded slides (reuses the carousel renderer)
via ffmpeg, with optional AI voiceover. Styles rotate based on which providers are configured:
  - animated : silent branded slideshow with crossfades            (free, needs ffmpeg)
  - narrated : same visuals + OpenAI TTS voiceover                 (needs OPENAI_API_KEY)
  - ai       : AI text-to-video via Replicate                       (needs REPLICATE_API_TOKEN)
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import requests

from . import carousel, config, llm


def _ffmpeg() -> str:
    exe = shutil.which("ffmpeg") or "/Users/apple/bin/ffmpeg"
    if not Path(exe).exists() and not shutil.which("ffmpeg"):
        raise RuntimeError("ffmpeg not found")
    return shutil.which("ffmpeg") or exe


def available_styles() -> list[str]:
    styles = ["animated"]
    if config.env("OPENAI_API_KEY"):
        styles.append("narrated")
    if config.env("REPLICATE_API_TOKEN"):
        styles.append("ai")
    return styles


def pick_style(n_published: int) -> str:
    """Rotate through whatever styles are available so they alternate over time."""
    styles = available_styles()
    forced = config.env("VIDEO_STYLE")
    if forced in styles:
        return forced
    return styles[n_published % len(styles)]


def _slideshow(pngs: list[Path], out: Path, per: float = 4.0, xf: float = 0.6) -> Path:
    """Crossfade slideshow MP4 (1080x1350, H.264) from the slide PNGs."""
    n = len(pngs)
    cmd = [_ffmpeg(), "-y"]
    for p in pngs:
        cmd += ["-loop", "1", "-t", f"{per}", "-i", str(p)]
    if n == 1:
        filt = "[0:v]fps=30,format=yuv420p[vout]"
    else:
        parts, prev = [], "[0:v]"
        for i in range(1, n):
            offset = i * (per - xf)
            label = "[vout]" if i == n - 1 else f"[vx{i}]"
            parts.append(f"{prev}[{i}:v]xfade=transition=fade:duration={xf}:offset={offset:.3f}{label}")
            prev = label
        filt = ";".join(parts) + ";[vout]fps=30,format=yuv420p[vfin]"
    vmap = "[vfin]" if n > 1 else "[vout]"
    cmd += ["-filter_complex", filt, "-map", vmap,
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", "30", "-movflags", "+faststart", str(out)]
    subprocess.run(cmd, check=True, capture_output=True)
    return out


def _tts(script: str, out_mp3: Path) -> Path | None:
    """OpenAI TTS -> mp3. Returns None if no key."""
    key = config.env("OPENAI_API_KEY")
    if not key:
        return None
    r = requests.post(
        "https://api.openai.com/v1/audio/speech",
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        json={"model": config.env("OPENAI_TTS_MODEL", "gpt-4o-mini-tts"),
              "voice": config.env("OPENAI_TTS_VOICE", "onyx"), "input": script[:4000]},
        timeout=120)
    r.raise_for_status()
    out_mp3.write_bytes(r.content)
    return out_mp3


def _mux(video: Path, audio: Path, out: Path) -> Path:
    subprocess.run([_ffmpeg(), "-y", "-i", str(video), "-i", str(audio),
                    "-c:v", "copy", "-c:a", "aac", "-shortest", str(out)],
                   check=True, capture_output=True)
    return out


def _narration_script(spec: dict) -> str:
    lines = []
    for s in spec["slides"]:
        if s.get("headline"):
            lines.append(s["headline"])
        if s.get("sub"):
            lines.append(s["sub"])
        for b in s.get("bullets", [])[:3]:
            lines.append(b)
    return ". ".join(lines)


def make_video(topic: dict, style: str, slug: str, date: str) -> tuple[Path | None, str, str]:
    """Return (path|None, status, style). Reuses the carousel slide spec + renderer for frames."""
    try:
        spec = carousel.make_spec(topic)
        out_dir = config.CAROUSELS.parent / "videos" / date
        out_dir.mkdir(parents=True, exist_ok=True)
        _, pngs = carousel.render(spec, out_dir / slug)

        silent = out_dir / f"{slug}.mp4"
        if style == "narrated" and config.env("OPENAI_API_KEY"):
            audio = _tts(_narration_script(spec), out_dir / f"{slug}.mp3")
            if audio:
                # pace slides to the narration length
                per = 4.0
                try:
                    dur = float(subprocess.run(
                        [_ffmpeg().replace("ffmpeg", "ffprobe"), "-v", "error", "-show_entries",
                         "format=duration", "-of", "default=nw=1:nk=1", str(audio)],
                        check=True, capture_output=True, text=True).stdout.strip())
                    per = max(3.0, dur / max(1, len(pngs)) + 0.6)
                except Exception:
                    pass
                _slideshow(pngs, silent, per=per)
                final = out_dir / f"{slug}-narrated.mp4"
                _mux(silent, audio, final)
                return final, "generated (narrated)", "narrated"
            # no audio -> fall through to animated

        if style == "ai" and config.env("REPLICATE_API_TOKEN"):
            # Placeholder: AI text-to-video provider wiring goes here once a model is chosen.
            # Fall back to animated for now so the lane still ships a video.
            pass

        _slideshow(pngs, silent)
        return silent, "generated (animated)", "animated"
    except Exception as e:
        return None, f"video generation failed: {e}", style
