"""Motion-graphics video lane. Builds an engaging MP4 (not static slides) from the day's
AI-news topic: AI-generated image backgrounds with Ken Burns motion, animated text overlays,
crossfade transitions, and a free AI voiceover.

Styles rotate based on configured providers:
  - animated : motion video, no voiceover                         (free)
  - narrated : motion video + edge-tts voiceover                  (free; OpenAI TTS optional)
  - ai       : AI text-to-video via Replicate                     (needs REPLICATE_API_TOKEN)
"""
from __future__ import annotations

import random
import shutil
import subprocess
import urllib.parse
from io import BytesIO
from pathlib import Path

import requests
from PIL import Image, ImageDraw

from . import carousel, config, llm

W, H = 1080, 1350
NAVY, EMERALD, ORANGE, WHITE = (10, 25, 47), (80, 200, 120), (255, 165, 0), (255, 255, 255)
BG_SUFFIX = (
    " Cinematic editorial photograph, moody dramatic lighting, deep navy and teal tones with a subtle "
    "emerald highlight, shallow depth of field, minimal and premium. No text, no watermark, no robots, "
    "no glowing brains, no circuit boards."
)


def _ffmpeg() -> str:
    exe = shutil.which("ffmpeg")
    if not exe:
        raise RuntimeError("ffmpeg not found")
    return exe


def _ffprobe() -> str:
    return shutil.which("ffprobe") or _ffmpeg().replace("ffmpeg", "ffprobe")


def _have_edge_tts() -> bool:
    try:
        import edge_tts  # noqa: F401
        return True
    except Exception:
        return False


def available_styles() -> list[str]:
    styles = ["animated"]
    if _have_edge_tts() or config.env("OPENAI_API_KEY"):
        styles.append("narrated")
    if config.env("REPLICATE_API_TOKEN"):
        styles.append("ai")
    return styles


def pick_style(n_published: int) -> str:
    styles = available_styles()
    forced = config.env("VIDEO_STYLE")
    if forced in styles:
        return forced
    return styles[n_published % len(styles)]


# ---------- script ----------

def make_script(topic: dict) -> dict:
    system = llm.brand_context() + (
        "\n\nTASK: write a short, punchy LinkedIn VIDEO script about this AI-news topic. "
        "4-6 scenes. Each scene has a very short on-screen line (<= 9 words, no hashtags) and a concrete "
        "editorial image concept (a real-world scene/metaphor, no text/robots/UI). Scene 1 is the hook; "
        "the last is a soft CTA in Paul's voice. Also write a flowing voiceover NARRATION that is punchy and "
        "spoken, about 60-80 seconds when read aloud (roughly 140-170 words), no emojis, tracking the scenes. "
        "State only verified facts; invent nothing."
    )
    facts = f"\nVERIFIED FACTS: {topic['verifiedFacts']}" if topic.get("verifiedFacts") else ""
    user = (
        f"TOPIC: {topic['topic']}\nKEY IDEA: {topic.get('keyIdea','')}\nWHY NOW: {topic.get('whyNow','')}{facts}\n"
        'Return JSON: {"title":str,"scenes":[{"kicker":str,"line":str,"imagePrompt":str}],"narration":str}'
    )
    spec = llm.complete_obj(system, user, max_tokens=1600, temperature=0.7)
    spec["scenes"] = [s for s in spec.get("scenes", []) if s.get("line")][:6] or [
        {"kicker": "AI NEWS", "line": topic["topic"][:60], "imagePrompt": "a quiet modern office at dawn"}]
    return spec


# ---------- visuals ----------

def _bg_image(prompt: str, out: Path, seed: int) -> Path:
    import time
    q = urllib.parse.quote((prompt + BG_SUFFIX)[:1800], safe="")
    token = config.env("POLLINATIONS_TOKEN")
    if token:
        # Token tier: flux quality + nologo + higher rate limits.
        url = f"https://image.pollinations.ai/prompt/{q}?width={W}&height={H}&model=flux&nologo=true&seed={seed}"
        headers = {"Authorization": f"Bearer {token}"}
        crop = 0.0
    else:
        # Free anonymous tier: default model; crop removes the watermark.
        url = f"https://image.pollinations.ai/prompt/{q}?width={W}&height={H}&seed={seed}"
        headers = {}
        crop = 0.06
    last = None
    for attempt in range(4):
        try:
            r = requests.get(url, headers=headers, timeout=120)
            if r.status_code in (402, 429, 500, 503):
                last = f"{r.status_code}"
                time.sleep(4 * (attempt + 1))
                continue
            r.raise_for_status()
            im = Image.open(BytesIO(r.content)).convert("RGB")
            w, h = im.size
            if crop:
                im = im.crop((0, 0, w, h - max(1, int(h * crop))))
            im.resize((W, H)).save(out)
            return out
        except requests.exceptions.RequestException as e:
            last = str(e)
            time.sleep(4 * (attempt + 1))
    raise RuntimeError(f"pollinations background failed after retries: {last}")


def _gradient_bg(out: Path, seed: int = 0) -> Path:
    """Fallback background: vertical brand gradient + a soft emerald glow (no network)."""
    from PIL import ImageChops
    random.seed(seed)
    base = Image.new("RGB", (W, H))
    bp = base.load()
    for y in range(H):
        t = y / H
        bp[0, y] = (0, 0, 0)
        row = (int(NAVY[0] + (2 - NAVY[0]) * t), int(NAVY[1] + (10 - NAVY[1]) * t), int(NAVY[2] + (26 - NAVY[2]) * t))
        for x in range(W):
            bp[x, y] = row
    glow = Image.new("RGB", (W, H), (0, 0, 0))
    gd = ImageDraw.Draw(glow)
    cx, cy = random.randint(W // 4, 3 * W // 4), random.randint(H // 5, H // 2)
    for rad in range(460, 0, -6):
        a = 60 * rad // 460
        gd.ellipse((cx - rad, cy - rad, cx + rad, cy + rad),
                   fill=(a * EMERALD[0] // 255, a * EMERALD[1] // 255, a * EMERALD[2] // 255))
    ImageChops.add(base, glow).save(out)
    return out


def _text_overlay(kicker: str, line: str, idx: int, total: int, out: Path) -> Path:
    """Transparent RGBA overlay: bottom gradient scrim + kicker + big headline + progress + brand mark."""
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    # bottom gradient scrim for legibility
    scrim_top = int(H * 0.45)
    for y in range(scrim_top, H):
        a = int(235 * (y - scrim_top) / (H - scrim_top))
        d.line([(0, y), (W, y)], fill=(NAVY[0], NAVY[1], NAVY[2], a))
    pad = 80
    y = int(H * 0.60)
    # emerald accent bar
    d.rectangle((pad, y, pad + 70, y + 8), fill=EMERALD + (255,))
    y += 30
    d.text((pad, y), (kicker or "AI NEWS").upper(), font=carousel._font(34, "SemiBold"), fill=ORANGE + (255,))
    y += 72
    hf = carousel._font(82, "Bold")
    for ln in carousel._wrap(d, line, hf, W - 2 * pad):
        d.text((pad, y), ln, font=hf, fill=WHITE + (255,))
        y += int(hf.size * 1.14)
    # progress dots
    dotw = 26
    for i in range(total):
        cx = pad + i * dotw
        col = EMERALD + (255,) if i <= idx else (255, 255, 255, 90)
        d.ellipse((cx, H - 70, cx + 12, H - 58), fill=col)
    d.text((W - pad - 320, H - 74), "Lark AI  ·  Paul Charles", font=carousel._font(26, "Medium"),
           fill=(255, 255, 255, 170))
    img.save(out)
    return out


def _kenburns(frames: int, variant: int) -> str:
    """zoompan z/x/y expressions; variant changes the camera move so scenes feel distinct."""
    cx, cy = "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"
    moves = [
        (f"min(zoom+0.0012,1.20)", cx, cy),                                   # 0 slow zoom-in (center)
        ("1.16", f"(iw-iw/zoom)*on/{frames}", cy),                            # 1 pan left->right
        ("1.16", f"(iw-iw/zoom)*(1-on/{frames})", cy),                        # 2 pan right->left
        ("1.16", cx, f"(ih-ih/zoom)*on/{frames}"),                            # 3 pan top->bottom
    ]
    z, x, y = moves[variant % len(moves)]
    return f"zoompan=z='{z}':x='{x}':y='{y}':d={frames}:s={W}x{H}:fps=30"


def _scene_clip(bg: Path, overlay: Path, dur: float, out: Path, variant: int = 0) -> Path:
    """Ken Burns move on bg (zoompan makes frames from one still) + fade-in text overlay."""
    frames = max(2, int(dur * 30))
    filt = (
        f"[0:v]scale={int(W*1.25)}:{int(H*1.25)},{_kenburns(frames, variant)},setsar=1[kb];"
        f"[1:v]format=rgba,fps=30,fade=t=in:st=0.2:d=0.6:alpha=1,setsar=1[txt];"
        f"[kb][txt]overlay=0:0,format=yuv420p[v]"
    )
    subprocess.run([_ffmpeg(), "-y",
                    "-i", str(bg),                                   # bg: single frame -> zoompan makes motion
                    "-loop", "1", "-t", f"{dur}", "-i", str(overlay),  # overlay: looped so fade animates
                    "-filter_complex", filt, "-map", "[v]",
                    "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-r", "30",
                    "-pix_fmt", "yuv420p", "-t", f"{dur}", str(out)],
                   check=True, capture_output=True)
    return out


def _concat_xfade(clips: list[Path], out: Path, dur: float, xf: float = 0.5) -> Path:
    if len(clips) == 1:
        shutil.copy(clips[0], out)
        return out
    cmd = [_ffmpeg(), "-y"]
    for c in clips:
        cmd += ["-i", str(c)]
    parts, prev = [], "[0:v]"
    for i in range(1, len(clips)):
        offset = i * (dur - xf)
        label = "[vout]" if i == len(clips) - 1 else f"[x{i}]"
        parts.append(f"{prev}[{i}:v]xfade=transition=fade:duration={xf}:offset={offset:.3f}{label}")
        prev = label
    filt = ";".join(parts) + ";[vout]format=yuv420p[vf]"
    cmd += ["-filter_complex", filt, "-map", "[vf]", "-c:v", "libx264", "-r", "30",
            "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(out)]
    subprocess.run(cmd, check=True, capture_output=True)
    return out


# ---------- audio ----------

def _tts(script: str, out_mp3: Path) -> Path | None:
    """Prefer free edge-tts; fall back to OpenAI TTS if a key is set."""
    if _have_edge_tts():
        try:
            import asyncio
            import edge_tts
            voice = config.env("EDGE_TTS_VOICE", "en-US-GuyNeural")

            async def _gen():
                await edge_tts.Communicate(script[:4000], voice).save(str(out_mp3))

            asyncio.run(_gen())
            if out_mp3.exists() and out_mp3.stat().st_size > 2000:
                return out_mp3
        except Exception as e:
            print(f"[video] edge-tts failed, trying OpenAI: {e}")
    key = config.env("OPENAI_API_KEY")
    if not key:
        return None
    r = requests.post("https://api.openai.com/v1/audio/speech",
                      headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                      json={"model": config.env("OPENAI_TTS_MODEL", "gpt-4o-mini-tts"),
                            "voice": config.env("OPENAI_TTS_VOICE", "onyx"), "input": script[:4000]},
                      timeout=120)
    r.raise_for_status()
    out_mp3.write_bytes(r.content)
    return out_mp3


def _audio_duration(path: Path) -> float | None:
    try:
        return float(subprocess.run(
            [_ffprobe(), "-v", "error", "-show_entries", "format=duration",
             "-of", "default=nw=1:nk=1", str(path)], check=True, capture_output=True, text=True).stdout.strip())
    except Exception:
        return None


def _mux(video: Path, audio: Path, out: Path) -> Path:
    subprocess.run([_ffmpeg(), "-y", "-i", str(video), "-i", str(audio),
                    "-c:v", "copy", "-c:a", "aac", "-shortest", str(out)], check=True, capture_output=True)
    return out


# ---------- orchestration ----------

def make_video(topic: dict, style: str, slug: str, date: str) -> tuple[Path | None, str, str]:
    try:
        spec = make_script(topic)
        scenes = spec["scenes"]
        out_dir = config.CAROUSELS.parent / "videos" / date / slug
        out_dir.mkdir(parents=True, exist_ok=True)

        # Narration first (so we can pace scenes to the voice) when applicable.
        audio = None
        if style == "narrated":
            audio = _tts(spec.get("narration") or " ".join(s["line"] for s in scenes), out_dir / "vo.mp3")
        total_audio = _audio_duration(audio) if audio else None
        n = len(scenes)
        xf = 0.5
        if total_audio:
            # Pace scenes so total video length ~= narration length (so -shortest never truncates the voice).
            per = (total_audio + (n - 1) * xf) / n
            per = min(max(per, 3.0), 16.0)
        else:
            per = 4.0  # silent/animated: punchy ~4s scenes

        # With a Pollinations token: a distinct image per scene. Without: one image reused with
        # varied Ken Burns moves (anonymous tier rate-limits multiple calls). Gradient fallback either way.
        per_scene_images = bool(config.env("POLLINATIONS_TOKEN"))
        shared_bg = None
        if not per_scene_images:
            shared_bg = out_dir / "bg.png"
            try:
                _bg_image(scenes[0].get("imagePrompt", topic["topic"]), shared_bg, seed=random.randint(1, 10**6))
            except Exception as e:
                print(f"[video] bg image failed ({e}); using brand gradient")
                _gradient_bg(shared_bg, seed=random.randint(1, 10**6))

        clips = []
        for i, s in enumerate(scenes):
            if per_scene_images:
                bg = out_dir / f"bg{i}.png"
                try:
                    _bg_image(s.get("imagePrompt", topic["topic"]), bg, seed=random.randint(1, 10**6))
                except Exception as e:
                    print(f"[video] scene {i} bg failed ({e}); gradient")
                    _gradient_bg(bg, seed=random.randint(1, 10**6))
            else:
                bg = shared_bg
            ov = _text_overlay(s.get("kicker", "AI NEWS"), s["line"], i, len(scenes), out_dir / f"ov{i}.png")
            clips.append(_scene_clip(bg, ov, per, out_dir / f"scene{i}.mp4", variant=i))

        silent = out_dir / f"{slug}.mp4"
        _concat_xfade(clips, silent, dur=per)

        if style == "ai" and config.env("REPLICATE_API_TOKEN"):
            pass  # AI text-to-video provider wiring goes here; falls through to the motion video for now.

        if audio:
            final = out_dir / f"{slug}-narrated.mp4"
            _mux(silent, audio, final)
            return final, "generated (narrated motion)", "narrated"
        return silent, "generated (motion)", "animated"
    except Exception as e:
        return None, f"video generation failed: {e}", style
