"""Quote-card post lane: a tweet-style quote image (black card, avatar, verified name,
big quote) + an engagement-optimized caption (Lara Acosta style). Replaces the old
AI-scene image on the 'post' lane."""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

from . import carousel, config, llm

W, H = 1080, 1350
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
GRAY = (136, 153, 166)
TWITTER_BLUE = (29, 161, 242)
AVATAR_BG = (214, 197, 170)
NAME = "Paul Charles"
HANDLE = "@Paul-Charleslark29"
PAD = 70


def _circle_avatar(d: ImageDraw.ImageDraw, img: Image.Image, cx: int, cy: int, r: int) -> None:
    av_path = None
    for p in (config.ROOT / "assets" / "avatar.jpg", config.ROOT / "assets" / "avatar.png",
              config.ROOT / "assets" / "avatar.jpeg"):
        if p.exists():
            av_path = p
            break
    if av_path:
        av = Image.open(av_path).convert("RGB").resize((2 * r, 2 * r))
        mask = Image.new("L", (2 * r, 2 * r), 0)
        ImageDraw.Draw(mask).ellipse((0, 0, 2 * r, 2 * r), fill=255)
        img.paste(av, (cx - r, cy - r), mask)
    else:
        d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=AVATAR_BG)
        f = carousel._font(int(r * 0.9), "Bold")
        tw = d.textlength("PC", font=f)
        d.text((cx - tw / 2, cy - r * 0.62), "PC", font=f, fill=(60, 50, 40))


def _verified(d: ImageDraw.ImageDraw, cx: int, cy: int, r: int) -> None:
    d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=TWITTER_BLUE)
    s = r * 0.55
    d.line([(cx - s * 0.6, cy), (cx - s * 0.1, cy + s * 0.55), (cx + s * 0.7, cy - s * 0.5)],
           fill=WHITE, width=max(3, int(r * 0.22)), joint="curve")


def render_card(quote: str, out: Path) -> Path:
    img = Image.new("RGB", (W, H), BLACK)
    d = ImageDraw.Draw(img)

    ar = 78
    acx, acy = PAD + ar, 300
    _circle_avatar(d, img, acx, acy, ar)

    name_f = carousel._font(58, "Bold")
    nx = acx + ar + 34
    d.text((nx, acy - 56), NAME, font=name_f, fill=WHITE)
    nw = d.textlength(NAME, font=name_f)
    _verified(d, int(nx + nw + 34), int(acy - 28), 26)
    d.text((nx, acy + 14), HANDLE, font=carousel._font(40, "Medium"), fill=GRAY)

    qf = carousel._font(104, "Bold")
    lines = carousel._wrap(d, quote, qf, W - 2 * PAD)
    lh = int(qf.size * 1.1)
    y = 620
    for ln in lines:
        d.text((PAD, y), ln, font=qf, fill=WHITE)
        y += lh
    img.save(out)
    return out


def generate(recent_topics: list[str]) -> dict:
    """Return {quote, caption, firstComment}. Quote <=13 words, one sentence, brand-aligned."""
    system = llm.brand_context() + (
        "\n\nTASK: produce a SHORT original quote-card for Paul Charles plus an engagement caption.\n"
        "QUOTE RULES: one sentence, MAX 13 words, modern AI/automation wisdom in Paul's own voice, "
        "punchy and quotable, no hashtags/emojis/quotation marks, not a tired platitude, not attributed to anyone else.\n"
        "CAPTION RULES (Lara Acosta engagement style): open with a scroll-stopping one-line hook; then short, "
        "skimmable, left-aligned lines (F-shaped: front-load the strong words, one idea per line, generous line breaks); "
        "teach ONE concrete idea tied to the quote; write like you think, not corporate; end with a specific question "
        "that invites a reply. Under 1100 characters. At most 2 hashtags or none. No em dashes.\n"
        "FIRST COMMENT: a short thoughtful comment Paul can pin under his own post that adds one more angle and "
        "explicitly invites discussion (Acosta self-comment tactic). One or two sentences."
    )
    user = ("Avoid repeating these recent themes:\n- " + "\n- ".join(recent_topics[:14]) +
            '\n\nReturn JSON: {"quote":str,"caption":str,"firstComment":str,"topic":str (3-6 word label of the quote theme)}')
    out = llm.complete_obj(system, user, max_tokens=1200, temperature=0.9)
    # Enforce the 13-word / one-sentence cap defensively.
    q = " ".join((out.get("quote") or "").replace("\n", " ").split())
    q = q.split(". ")[0].rstrip(".")
    if len(q.split()) > 13:
        q = " ".join(q.split()[:13])
    out["quote"] = q
    return out
