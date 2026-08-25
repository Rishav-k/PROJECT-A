"""
carousel.py — Pulse Media Vintage-Modern Editorial Carousel Generator
Produces bold, high-contrast 1080×1080 Instagram carousel posts matching the
signature 4-color retro-modern editorial aesthetic:
  • Color 1: #DF301C (Deep Terracotta / Crimson Red)
  • Color 2: #EF8D32 (Warm Tangerine / Ochre Orange)
  • Color 3: #FEF3DC (Vintage Cream / Eggshell White)
  • Color 4: #3FA9BE (Ocean Turquoise / Teal Blue)
"""

from __future__ import annotations

import io
import os
import re
import sys
import math
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

try:
    from PIL import Image, ImageDraw, ImageFont, ImageEnhance
except ImportError:
    print("❌ Pillow not installed. Run: pip3 install Pillow")
    sys.exit(1)

sys.path.insert(0, os.path.dirname(__file__))

# ── Output directory ──────────────────────────────────────────────────────────
OUTPUT_DIR = Path(__file__).parent / "output" / "images"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

SIZE = 1080

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
    "finpulse":   ("MARKET PULSE:", "FINANCIAL INTELLIGENCE"),
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


# ── Helper Vector Graphic Renderers ──────────────────────────────────────────

def draw_top_handle(draw: ImageDraw.ImageDraw, handle: str, color: tuple):
    font = _get_font("din_alt", 26)
    draw.text((SIZE // 2, 45), handle, fill=color, font=font, anchor="mt")


def draw_bottom_handle(draw: ImageDraw.ImageDraw, handle: str, color: tuple):
    font = _get_font("din_alt", 24)
    draw.text((SIZE // 2, SIZE - 55), handle, fill=color, font=font, anchor="mb")


def draw_ribbon_banner(draw: ImageDraw.ImageDraw, cx: int, cy: int, width: int, height: int,
                       fill: tuple, text: str, text_color: tuple, font: ImageFont.FreeTypeFont):
    """Draws a stylish vintage-modern folded ribbon banner."""
    x0 = cx - width // 2
    x1 = cx + width // 2
    y0 = cy - height // 2
    y1 = cy + height // 2

    # Fold shadows
    fold_w = 24
    draw.polygon([(x0 - fold_w, y0 + 12), (x0, y0), (x0, y1), (x0 - fold_w, y1 + 12)], fill=(int(fill[0]*0.7), int(fill[1]*0.7), int(fill[2]*0.7)))
    draw.polygon([(x1 + fold_w, y0 + 12), (x1, y0), (x1, y1), (x1 + fold_w, y1 + 12)], fill=(int(fill[0]*0.7), int(fill[1]*0.7), int(fill[2]*0.7)))

    # Main ribbon body
    draw.rectangle([(x0, y0), (x1, y1)], fill=fill)
    draw.text((cx, cy + 2), text, fill=text_color, font=font, anchor="mm")


def draw_speech_bubble(draw: ImageDraw.ImageDraw, box: tuple, fill: tuple, outline: tuple, width: int = 5):
    """Draws a rounded speech bubble with a bottom tail."""
    x0, y0, x1, y1 = box
    draw.rounded_rectangle([(x0, y0), (x1, y1)], radius=32, fill=fill, outline=outline, width=width)
    # Tail
    tx = x1 - 120
    draw.polygon([(tx, y1 - 2), (tx + 50, y1 - 2), (tx + 30, y1 + 35)], fill=fill)
    draw.line([(tx, y1 - 2), (tx + 30, y1 + 35)], fill=outline, width=width)
    draw.line([(tx + 50, y1 - 2), (tx + 30, y1 + 35)], fill=outline, width=width)


def draw_growth_chart(draw: ImageDraw.ImageDraw, x0: int, y0: int, x1: int, y1: int, color: tuple, width: int = 6):
    """Draws an exponential upward chart curve with arrowhead and stars."""
    # Axes
    draw.line([(x0, y0), (x0, y1), (x1, y1)], fill=color, width=width)

    # Smooth curve
    points = []
    steps = 30
    for i in range(steps + 1):
        t = i / steps
        px = x0 + t * (x1 - x0)
        # Exponential curve
        py = y1 - (t ** 2.2) * (y1 - y0)
        points.append((px, py))

    for i in range(len(points) - 1):
        draw.line([points[i], points[i+1]], fill=color, width=width + 2)

    # Arrow head at end
    ex, ey = points[-1]
    draw.polygon([(ex, ey), (ex - 22, ey + 4), (ex - 4, ey + 22)], fill=color)

    # Sparkling stars
    for sx, sy in [(x0 + 260, y1 - 140), (x1 - 120, y0 + 120)]:
        draw_star(draw, sx, sy, 16, color)


def draw_star(draw: ImageDraw.ImageDraw, cx: int, cy: int, r: int, color: tuple):
    draw.polygon([(cx, cy - r), (cx + r//3, cy - r//3), (cx + r, cy), (cx + r//3, cy + r//3),
                  (cx, cy + r), (cx - r//3, cy + r//3), (cx - r, cy), (cx - r//3, cy - r//3)], fill=color)


def draw_swipe_arrow(draw: ImageDraw.ImageDraw, cx: int, cy: int, color: tuple):
    """Draws a bold stylish curved arrow pointing right."""
    draw.arc([(cx - 70, cy - 30), (cx + 30, cy + 50)], start=160, end=320, fill=color, width=14)
    draw.polygon([(cx + 30, cy - 5), (cx + 55, cy + 15), (cx + 25, cy + 35)], fill=color)


def draw_swipe_pill(draw: ImageDraw.ImageDraw, cx: int, cy: int, fill: tuple, text_color: tuple):
    font = _get_font("din_alt", 26)
    draw.rounded_rectangle([(cx - 90, cy - 24), (cx + 90, cy + 24)], radius=24, fill=fill)
    draw.text((cx, cy), "SWIPE ➔", fill=text_color, font=font, anchor="mm")


def wrap_text(text: str, font: ImageFont.FreeTypeFont, max_width: int) -> List[str]:
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
# 5 SLIDE GENERATORS
# ─────────────────────────────────────────────────────────────────────────────

def create_slide_1_hero(article: Dict[str, Any], page: str) -> Image.Image:
    """SLIDE 1: Deep Terracotta Red (#DF301C) Lead/Hero Card"""
    im = Image.new("RGB", (SIZE, SIZE), C_RED)
    draw = ImageDraw.Draw(im)
    handle = PAGE_HANDLES.get(page, "finpulse.daily")
    draw_top_handle(draw, handle, C_CREAM)

    h_lead, h_sub = PAGE_TITLES.get(page, ("MARKET PULSE:", "BREAKING INTELLIGENCE"))
    font_lead = _get_font("impact", 76)
    font_sub  = _get_font("din_cond", 54)
    font_title = _get_font("din_cond", 44)
    font_body = _get_font("body", 24)

    draw.text((SIZE // 2, 105), h_lead, fill=C_CREAM, font=font_lead, anchor="mt")
    draw.text((SIZE // 2, 195), h_sub, fill=C_ORANGE, font=font_sub, anchor="mt")

    # Center card in Cream #FEF3DC
    card_box = (80, 275, SIZE - 80, 810)
    draw.rounded_rectangle(card_box, radius=24, fill=C_CREAM, outline=C_DARK, width=6)

    # Title in card
    title = article.get("title", "Market Intelligence Report")
    title_lines = wrap_text(title, font_title, 820)[:4]
    y = 320
    for line in title_lines:
        draw.text((SIZE // 2, y), line.upper(), fill=C_DARK, font=font_title, anchor="mt")
        y += 52

    # Summary snippet
    summary = article.get("summary", "")
    if summary:
        sum_lines = wrap_text(summary, font_body, 800)[:3]
        y += 20
        for sline in sum_lines:
            draw.text((SIZE // 2, y), sline, fill=C_MAROON, font=font_body, anchor="mt")
            y += 34

    # Source tag & trigger
    src = article.get("source_name", "Official Source")
    draw.text((SIZE // 2, 755), f"SOURCE: {src.upper()}", fill=C_DARK, font=_get_font("din_alt", 22), anchor="mt")

    # Bottom directional arrow
    draw_swipe_arrow(draw, SIZE // 2, 890, C_TEAL)
    draw_bottom_handle(draw, handle, C_CREAM)
    return im


def create_slide_2_breakdown(article: Dict[str, Any], page: str, caption_data: Dict[str, Any]) -> Image.Image:
    """SLIDE 2: Vintage Cream (#FEF3DC) Breakdown with Tangerine Ribbon"""
    im = Image.new("RGB", (SIZE, SIZE), C_CREAM)
    draw = ImageDraw.Draw(im)
    handle = PAGE_HANDLES.get(page, "finpulse.daily")
    draw_top_handle(draw, handle, C_RED)

    font_head = _get_font("impact", 72)
    font_sub  = _get_font("din_cond", 52)
    font_ribbon = _get_font("impact", 36)
    font_bullet = _get_font("body", 28)

    draw.text((SIZE // 2, 105), "THE BREAKDOWN:", fill=C_RED, font=font_head, anchor="mt")
    draw.text((SIZE // 2, 190), "WHAT HAPPENED & WHY IT MATTERS", fill=C_MAROON, font=font_sub, anchor="mt")

    # Ribbon Banner in Tangerine Orange #EF8D32
    draw_ribbon_banner(draw, SIZE // 2, 285, 680, 68, C_ORANGE, "CRITICAL DEVELOPMENTS", C_DARK, font_ribbon)

    # Main content box
    draw.rounded_rectangle([(80, 360), (SIZE - 80, 930)], radius=20, fill=C_WHITE, outline=C_DARK, width=5)

    analysis_txt = caption_data.get("analysis") or article.get("summary", "")
    lines = wrap_text(analysis_txt, font_bullet, 800)[:7]
    if not lines:
        lines = [article.get("title", "Breaking market news update.")]

    y = 410
    for line in lines:
        draw.text((120, y), line, fill=C_DARK, font=font_bullet)
        y += 42

    # Key takeaways pills
    y = max(y + 30, 720)
    for label in ["Direct portfolio & market relevance", "Key institutional players monitoring closely"]:
        draw.rounded_rectangle([(120, y), (SIZE - 120, y + 54)], radius=12, fill=C_CREAM, outline=C_MAROON, width=2)
        draw.ellipse([(140, y + 20), (154, y + 34)], fill=C_ORANGE)
        draw.text((170, y + 14), label, fill=C_DARK, font=_get_font("din_alt", 22))
        y += 66

    draw_bottom_handle(draw, handle, C_RED)
    return im


def create_slide_3_pros_cons(article: Dict[str, Any], page: str, caption_data: Dict[str, Any]) -> Image.Image:
    """SLIDE 3: Ocean Teal (#3FA9BE) Matrix with Winners & Risks"""
    im = Image.new("RGB", (SIZE, SIZE), C_TEAL)
    draw = ImageDraw.Draw(im)
    handle = PAGE_HANDLES.get(page, "finpulse.daily")
    draw_top_handle(draw, handle, C_CREAM)

    font_head = _get_font("impact", 72)
    font_sub  = _get_font("din_cond", 52)
    font_card_head = _get_font("din_cond", 36)
    font_bullet = _get_font("body", 23)

    draw.text((SIZE // 2, 105), "MARKET IMPACT MATRIX", fill=C_CREAM, font=font_head, anchor="mt")
    draw.text((SIZE // 2, 190), "WINNERS VS. RISKS IN PLAY", fill=C_CREAM, font=font_sub, anchor="mt")

    # Left Card: Positive / Beneficiaries (Cream #FEF3DC)
    draw.rounded_rectangle([(80, 270), (520, 870)], radius=20, fill=C_CREAM, outline=C_DARK, width=5)
    draw.rectangle([(80, 270), (520, 335)], fill=C_RED)
    draw.text((300, 290), "WHO BENEFITS & UPSIDES", fill=C_CREAM, font=font_card_head, anchor="mt")

    pros = caption_data.get("pros") or ["Favorable rate trajectory & earnings", "Strong sector momentum", "Institutional accumulation"]
    y = 360
    for p in pros[:4]:
        for pline in wrap_text(f"• {p}", font_bullet, 400)[:3]:
            draw.text((105, y), pline, fill=C_DARK, font=font_bullet)
            y += 34
        y += 10

    # Right Card: Risks / Losers (Cream #FEF3DC)
    draw.rounded_rectangle([(560, 270), (1000, 870)], radius=20, fill=C_CREAM, outline=C_DARK, width=5)
    draw.rectangle([(560, 270), (1000, 335)], fill=C_MAROON)
    draw.text((780, 290), "RISKS & HEADWINDS", fill=C_CREAM, font=font_card_head, anchor="mt")

    cons = caption_data.get("cons") or ["Volatility on macro headlines", "Supply or valuation pressure", "Policy uncertainty"]
    y = 360
    for c in cons[:4]:
        for cline in wrap_text(f"• {c}", font_bullet, 400)[:3]:
            draw.text((585, y), cline, fill=C_DARK, font=font_bullet)
            y += 34
        y += 10

    # Swipe Pill
    draw_swipe_pill(draw, SIZE // 2, 930, C_CREAM, C_DARK)
    draw_bottom_handle(draw, handle, C_CREAM)
    return im


def create_slide_4_quote(article: Dict[str, Any], page: str, caption_data: Dict[str, Any]) -> Image.Image:
    """SLIDE 4: Warm Tangerine (#EF8D32) Quote & Growth Curve"""
    im = Image.new("RGB", (SIZE, SIZE), C_ORANGE)
    draw = ImageDraw.Draw(im)
    handle = PAGE_HANDLES.get(page, "finpulse.daily")
    draw_top_handle(draw, handle, C_CREAM)

    font_quote = _get_font("impact", 54)
    font_author = _get_font("din_cond", 40)

    # Large Retro Speech Bubble in Cream #FEF3DC
    bubble_box = (80, 120, SIZE - 80, 520)
    draw_speech_bubble(draw, bubble_box, C_CREAM, C_DARK, width=6)

    # Quote text
    quote_text = f"\"{article.get('title', 'Smart investors position ahead of the crowd.')}\""
    qlines = wrap_text(quote_text.upper(), font_quote, 820)[:4]
    y = 180
    for ql in qlines:
        draw.text((SIZE // 2, y), ql, fill=C_DARK, font=font_quote, anchor="mt")
        y += 62

    draw.text((SIZE // 2, y + 16), f"— {article.get('source_name', 'RESEARCH DESK').upper()}", fill=C_MAROON, font=font_author, anchor="mt")

    # Exponential Growth Curve Chart below
    draw_growth_chart(draw, 140, 620, SIZE - 140, 890, C_CREAM, width=7)

    draw_bottom_handle(draw, handle, C_CREAM)
    return im


def create_slide_5_cta(article: Dict[str, Any], page: str, caption_data: Dict[str, Any]) -> Image.Image:
    """SLIDE 5: Deep Terracotta Red (#DF301C) Bottom Line & CTA"""
    im = Image.new("RGB", (SIZE, SIZE), C_RED)
    draw = ImageDraw.Draw(im)
    handle = PAGE_HANDLES.get(page, "finpulse.daily")
    draw_top_handle(draw, handle, C_CREAM)

    font_head = _get_font("impact", 72)
    font_sub  = _get_font("din_cond", 52)
    font_cta  = _get_font("impact", 56)
    font_body = _get_font("body", 26)

    draw.text((SIZE // 2, 105), "THE BOTTOM LINE:", fill=C_CREAM, font=font_head, anchor="mt")
    draw.text((SIZE // 2, 190), "STRATEGIC KEY TAKEAWAYS", fill=C_ORANGE, font=font_sub, anchor="mt")

    # Action Card in Cream #FEF3DC
    draw.rounded_rectangle([(80, 270), (SIZE - 80, 600)], radius=24, fill=C_CREAM, outline=C_DARK, width=6)
    y = 310
    takeaways = [
        "1️⃣ Stay disciplined — focus on structural secular leaders",
        "2️⃣ Volatility creates asymmetric risk/reward entry points",
        "3️⃣ Track institutional flows and sector rotation closely"
    ]
    for tk in takeaways:
        for tkline in wrap_text(tk, font_body, 820)[:2]:
            draw.text((120, y), tkline, fill=C_DARK, font=font_body)
            y += 38
        y += 18

    # Big CTA Box in Tangerine #EF8D32
    draw.rounded_rectangle([(80, 640), (SIZE - 80, 890)], radius=24, fill=C_ORANGE, outline=C_CREAM, width=5)
    draw.text((SIZE // 2, 675), f"FOLLOW @{handle.upper()}", fill=C_CREAM, font=font_cta, anchor="mt")
    draw.text((SIZE // 2, 755), "Daily High-Conviction Market Intelligence", fill=C_DARK, font=_get_font("din_cond", 36), anchor="mt")
    draw.text((SIZE // 2, 820), "📌 Save this post & share with fellow investors", fill=C_CREAM, font=_get_font("din_alt", 24), anchor="mt")

    draw_bottom_handle(draw, handle, C_CREAM)
    return im


# ─────────────────────────────────────────────────────────────────────────────
# MAIN CAROUSEL GENERATOR
# ─────────────────────────────────────────────────────────────────────────────

def generate_carousel(article: Dict[str, Any], page: str = "finpulse",
                      caption: str = "", caption_data: Optional[Dict[str, Any]] = None) -> List[Path]:
    """Generates 5 JPEG slides (1080×1080) in the signature retro-modern 4-color aesthetic."""
    if caption_data is None:
        caption_data = {}

    art_id = article.get("id", "temp")
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    prefix = f"{page}_c{art_id}"

    s1 = create_slide_1_hero(article, page)
    s2 = create_slide_2_breakdown(article, page, caption_data)
    s3 = create_slide_3_pros_cons(article, page, caption_data)
    s4 = create_slide_4_quote(article, page, caption_data)
    s5 = create_slide_5_cta(article, page, caption_data)

    slides = [s1, s2, s3, s4, s5]
    paths = []

    print(f"  🎠 Generating {page} retro-modern 4-color carousel for article {art_id}…")
    for i, slide_img in enumerate(slides, 1):
        filename = f"{prefix}_s{i}_{ts}.jpg"
        out_path = OUTPUT_DIR / filename
        slide_img.save(out_path, "JPEG", quality=95, optimize=True)
        paths.append(out_path)
        print(f"     Slide {i}: {filename} ({out_path.stat().st_size // 1024}KB)")

    return paths


if __name__ == "__main__":
    test_article = {
        "id": 99,
        "title": "Debt Free Key: Smart Debt Repayment Strategies For 2026",
        "summary": "Automate your savings, pay yourself first, and leverage the power of compound interest to build long-term wealth.",
        "source_name": "FinPulse Research"
    }
    res = generate_carousel(test_article, "finpulse")
    print(f"Generated {len(res)} slides successfully!")
