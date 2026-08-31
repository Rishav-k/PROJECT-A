"""
image.py — Pulse Media Branded News Card Generator
Creates Instagram-ready 1080×1080 images using the signature 4-color retro-modern
aesthetic (#DF301C, #EF8D32, #FEF3DC, #3FA9BE) and the official FinPulse candlestick emblem.
"""

from __future__ import annotations

import io
import os
import re
import sys
import math
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional

try:
    from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance
except ImportError:
    print("❌ Pillow not installed. Run: pip3 install Pillow")
    sys.exit(1)

sys.path.insert(0, os.path.dirname(__file__))

SIZE = 1080
OUTPUT_DIR = Path(__file__).parent / "output" / "images"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
ASSETS_DIR = Path(__file__).parent / "assets"

# ── 4-Color Signature Palette ────────────────────────────────────────────────
C_RED     = (223, 48, 28)     # #DF301C - Primary Crimson/Terracotta
C_ORANGE  = (239, 141, 50)    # #EF8D32 - Warm Tangerine
C_CREAM   = (254, 243, 220)   # #FEF3DC - Vintage Eggshell / Cream
C_TEAL    = (63, 169, 190)    # #3FA9BE - Ocean Turquoise / Teal
C_DARK    = (28, 25, 23)      # #1C1917 - Slate Dark
C_MAROON  = (122, 26, 14)     # #7A1A0E - Deep Maroon
C_WHITE   = (255, 255, 255)

PAGE_HANDLES = {
    "finpulse":   "finpulse.daily",
    "techpulse":  "techpulse.daily",
    "corppulse":  "corppulse.daily",
    "worldpulse": "worldpulse.daily",
}

PAGE_TITLES = {
    "finpulse":   ("MARKET PULSE:", "BREAKING FINANCIAL NEWS"),
    "techpulse":  ("TECH PULSE:", "AI & INNOVATION RADAR"),
    "corppulse":  ("CORP PULSE:", "BUSINESS & STRATEGY"),
    "worldpulse": ("WORLD PULSE:", "GLOBAL AFFAIRS RADAR"),
}


# ── Font Loader ──────────────────────────────────────────────────────────────
def _get_font(style: str, size: int) -> ImageFont.FreeTypeFont:
    paths = {
        "impact": [
            "/System/Library/Fonts/Supplemental/Impact.ttf",
            "/System/Library/Fonts/Supplemental/DIN Condensed Bold.ttf",
            "/System/Library/Fonts/HelveticaNeue.ttc"
        ],
        "din_cond": [
            "/System/Library/Fonts/Supplemental/DIN Condensed Bold.ttf",
            "/System/Library/Fonts/Supplemental/Impact.ttf",
            "/System/Library/Fonts/HelveticaNeue.ttc"
        ],
        "din_alt": [
            "/System/Library/Fonts/Supplemental/DIN Alternate Bold.ttf",
            "/System/Library/Fonts/Supplemental/Futura.ttc",
            "/System/Library/Fonts/HelveticaNeue.ttc"
        ],
        "body": [
            "/System/Library/Fonts/HelveticaNeue.ttc",
            "/System/Library/Fonts/Helvetica.ttc",
            "/Library/Fonts/Arial.ttf"
        ]
    }
    for p in paths.get(style, paths["body"]):
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                pass
    return ImageFont.load_default()


def _load_emblem(target_size: int = 120) -> Optional[Image.Image]:
    """Loads and resizes the official FinPulse candlestick circular logo emblem."""
    emblem_path = ASSETS_DIR / "finpulse_emblem_trans.png"
    if not emblem_path.exists():
        emblem_path = ASSETS_DIR / "finpulse_logo_trans.png"
    if emblem_path.exists():
        try:
            emb = Image.open(emblem_path).convert("RGBA")
            emb.thumbnail((target_size, target_size), Image.Resampling.LANCZOS)
            return emb
        except Exception:
            pass
    return None


def wrap_text(text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    words = text.split()
    lines = []
    curr = []
    for w in words:
        test = " ".join(curr + [w])
        bbox = font.getbbox(test)
        w_px = bbox[2] - bbox[0]
        if w_px <= max_width:
            curr.append(w)
        else:
            if curr:
                lines.append(" ".join(curr))
            curr = [w]
    if curr:
        lines.append(" ".join(curr))
    return lines


# ─────────────────────────────────────────────────────────────────────────────
# NEWS CARD GENERATOR (1080×1080)
# ─────────────────────────────────────────────────────────────────────────────

def create_news_card(article: Dict[str, Any], page: str = "finpulse") -> Image.Image:
    """
    Creates a single standalone 1080×1080 Instagram post card in the 4-color palette
    featuring the official FinPulse candlestick emblem.
    """
    im = Image.new("RGB", (SIZE, SIZE), C_RED)
    draw = ImageDraw.Draw(im)
    handle = PAGE_HANDLES.get(page, "finpulse.daily")

    # 1. Header with Logo Emblem + Handle
    emblem = _load_emblem(110)
    if emblem:
        # Paste emblem at top center
        ew, eh = emblem.size
        ex = (SIZE - ew) // 2
        im.paste(emblem, (ex, 35), emblem)
        draw.text((SIZE // 2, 155), handle, fill=C_CREAM, font=_get_font("din_alt", 26), anchor="mt")
        top_offset = 200
    else:
        draw.text((SIZE // 2, 45), handle, fill=C_CREAM, font=_get_font("din_alt", 26), anchor="mt")
        top_offset = 110

    # 2. Section Header
    h_lead, h_sub = PAGE_TITLES.get(page, ("MARKET PULSE:", "BREAKING NEWS"))
    draw.text((SIZE // 2, top_offset), h_lead, fill=C_CREAM, font=_get_font("impact", 68), anchor="mt")
    draw.text((SIZE // 2, top_offset + 75), h_sub, fill=C_ORANGE, font=_get_font("din_cond", 48), anchor="mt")

    # 3. Main Center Card in Vintage Cream #FEF3DC (Clean Borderless)
    card_top = top_offset + 140
    card_bot = 875
    draw.rounded_rectangle([(70, card_top), (SIZE - 70, card_bot)], radius=28, fill=C_CREAM)

    # Headline inside card
    title = article.get("title", "Breaking Market Intelligence Report")
    font_title = _get_font("din_cond", 44)
    font_body  = _get_font("body", 25)

    title_lines = wrap_text(title, font_title, 820)[:4]
    ty = card_top + 35
    for tline in title_lines:
        draw.text((SIZE // 2, ty), tline.upper(), fill=C_DARK, font=font_title, anchor="mt")
        ty += 52

    # Summary
    summary = article.get("summary", "")
    if summary:
        ty += 15
        sum_lines = wrap_text(summary, font_body, 800)[:3]
        for sline in sum_lines:
            draw.text((SIZE // 2, ty), sline, fill=C_MAROON, font=font_body, anchor="mt")
            ty += 34

    # Source & Publisher Badge (Clean Solid White, no outline)
    src = article.get("source_name", "Official News Desk")
    draw.rounded_rectangle([(120, card_bot - 65), (SIZE - 120, card_bot - 18)], radius=12, fill=C_WHITE)
    draw.text((SIZE // 2, card_bot - 42), f"SOURCE: {src.upper()}", fill=C_DARK, font=_get_font("din_alt", 22), anchor="mm")

    # 4. Bottom CTA / Swipe Bar
    draw.text((SIZE // 2, 920), "FOLLOW @FINPULSE.DAILY • STAY AHEAD", fill=C_ORANGE, font=_get_font("impact", 36), anchor="mt")
    draw.text((SIZE // 2, 975), "Save & Share with Fellow Investors 📌", fill=C_CREAM, font=_get_font("din_alt", 22), anchor="mt")

    return im


def generate_image(article: Dict[str, Any], page: str = "finpulse") -> Path:
    """Main image generator called by news pipelines and dashboard."""
    art_id = article.get("id", "temp")
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{page}_{art_id}_{ts}.jpg"
    out_path = OUTPUT_DIR / filename

    img = create_news_card(article, page)
    img.save(out_path, "JPEG", quality=95, optimize=True)
    print(f"  🖼  Saved news card: {filename} ({out_path.stat().st_size // 1024}KB)")
    return out_path


def save_image_path(article_id: int, image_path: str, page: str = "finpulse"):
    """Saves image path to SQLite database."""
    try:
        from database.schema import get_connection
        conn = get_connection()
        conn.execute("UPDATE articles SET image_path=? WHERE id=?", (image_path, article_id))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"⚠️ Error saving image path to DB: {e}")


if __name__ == "__main__":
    test_article = {
        "id": 1,
        "title": "Dow Rises But S&P 500 Declines Following Global Sanctions Announcement",
        "summary": "Markets reacted with strong sector rotation as institutional buyers moved into private banking and AI hardware leaders.",
        "source_name": "MarketWatch"
    }
    p = generate_image(test_article, "finpulse")
    print(f"Generated test news card: {p}")
