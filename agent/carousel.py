"""Branded carousel: slide spec (LLM) -> PNG slides (Pillow) -> PDF. Palette per BRAND section 9."""
from __future__ import annotations

import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from . import config, llm

W, H = 1080, 1350
NAVY, EMERALD, ORANGE, WHITE = (10, 25, 47), (80, 200, 120), (255, 165, 0), (255, 255, 255)
FOOTER = "Lark AI Agency  |  Paul Charles"
# Per-weight fallbacks when Poppins isn't present. macOS (Arial/Helvetica) first, then Linux DejaVu.
_FALLBACKS_BY_WEIGHT = {
    "Bold": ["/System/Library/Fonts/Supplemental/Arial Bold.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"],
    "SemiBold": ["/System/Library/Fonts/Supplemental/Arial Bold.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"],
    "Medium": ["/System/Library/Fonts/Supplemental/Arial.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"],
    "Regular": ["/System/Library/Fonts/Supplemental/Arial.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"],
}


def _font(size: int, weight: str = "Bold") -> ImageFont.FreeTypeFont:
    for p in [config.FONTS / f"Poppins-{weight}.ttf", *map(Path, _FALLBACKS_BY_WEIGHT.get(weight, []))]:
        if p.exists():
            return ImageFont.truetype(str(p), size)
    # Last resort: Pillow's bundled TrueType honours size (unlike the legacy bitmap default).
    try:
        return ImageFont.truetype("DejaVuSans.ttf", size)
    except Exception:
        return ImageFont.load_default(size)


def make_spec(topic: dict) -> dict:
    system = llm.brand_context() + (
        "\n\nTASK: design an educational LinkedIn carousel (RUNBOOK carousel lane). 6-9 slides: hook -> what it is / why it's "
        "blowing up -> 3-6 teaching slides (mechanism, steps, lessons) -> practical takeaway -> CTA (last). The reader must leave "
        "knowing something usable. Teach the idea in Paul's voice; never copy source wording; state only verified facts; "
        "no invented stats or builds. Headlines <= 60 chars, bullets <= 80 chars, max 4 bullets per slide."
    )
    facts = f"\nVERIFIED FACTS: {topic['verifiedFacts']}" if topic.get("verifiedFacts") else ""
    user = (
        f"TOPIC: {topic['topic']}\nKEY IDEA: {topic.get('keyIdea','')}\nWHY NOW: {topic.get('whyNow','')}{facts}\n"
        'Return JSON: {"title":str,"slides":[{"kicker":str,"headline":str,"sub":str,"bullets":[str]}]}. '
        'Last slide kicker must be exactly "CTA".'
    )
    spec = llm.complete_obj(system, user, max_tokens=2500, temperature=0.6)
    if spec["slides"][-1].get("kicker") != "CTA":
        spec["slides"][-1]["kicker"] = "CTA"
    return spec


def _wrap(draw, text, font, width):
    words, lines, cur = text.split(), [], ""
    for w in words:
        t = f"{cur} {w}".strip()
        if draw.textlength(t, font=font) <= width:
            cur = t
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def _slide(s: dict, idx: int, total: int) -> Image.Image:
    cta = s.get("kicker") == "CTA"
    bg = EMERALD if cta else NAVY
    fg = NAVY if cta else WHITE
    accent = WHITE if cta else EMERALD
    img = Image.new("RGB", (W, H), bg)
    d = ImageDraw.Draw(img)
    pad = 90
    # organic corner shape (rounded, restrained)
    d.ellipse((W - 240, -280, W + 280, 200), fill=(EMERALD if not cta else (60, 170, 100)))
    y = 150
    d.text((pad, y), s.get("kicker", "").upper(), font=_font(30, "SemiBold"), fill=ORANGE if not cta else NAVY)
    y += 110
    hf = _font(78 if idx == 0 else 64, "Bold")
    for line in _wrap(d, s.get("headline", ""), hf, W - 2 * pad):
        d.text((pad, y), line, font=hf, fill=fg)
        y += int(hf.size * 1.25)
    y += 30
    if s.get("sub"):
        sf = _font(38, "Regular")
        for line in _wrap(d, s["sub"], sf, W - 2 * pad):
            d.text((pad, y), line, font=sf, fill=fg)
            y += 54
        y += 20
    bf = _font(40, "Medium")
    for b in s.get("bullets", [])[:4]:
        d.ellipse((pad, y + 14, pad + 16, y + 30), fill=accent)
        for j, line in enumerate(_wrap(d, b, bf, W - 2 * pad - 50)):
            d.text((pad + 44, y), line, font=bf, fill=fg)
            y += 56
        y += 18
    d.text((pad, H - 110), FOOTER if cta else f"{idx + 1}/{total}", font=_font(30, "Medium"), fill=fg)
    return img


def render(spec: dict, out_dir: Path) -> tuple[Path, list[Path]]:
    out_dir.mkdir(parents=True, exist_ok=True)
    slides = spec["slides"]
    imgs = [_slide(s, i, len(slides)) for i, s in enumerate(slides)]
    pngs = []
    for i, im in enumerate(imgs, 1):
        p = out_dir / f"slide-{i:02d}.png"
        im.save(p)
        pngs.append(p)
    pdf = out_dir / "carousel.pdf"
    Image.init()  # make sure the JPEG plugin is registered for the PDF writer
    imgs[0].save(pdf, "PDF", save_all=True, append_images=imgs[1:], resolution=100.0)
    return pdf, pngs


def review(pngs: list[Path], topic: str) -> dict:
    """Vision check on slide 1 and a middle slide (RUNBOOK slide build step 3)."""
    probs = []
    for p in (pngs[0], pngs[len(pngs) // 2]):
        v = llm.vision_json(
            "You review LinkedIn carousel slides. Fail on text overflow/clipping, low contrast, clutter, or typos.",
            f"Topic: {topic}\nReturn JSON: {{\"pass\":bool,\"problems\":[str]}}", p)
        if not v.get("pass"):
            probs += v.get("problems", [])
    return {"pass": not probs, "problems": probs}
