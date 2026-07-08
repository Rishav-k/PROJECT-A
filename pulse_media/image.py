"""
image.py — Pulse Media Branded News Card Generator
Creates Instagram-ready 1080x1080 images from article data.

Layout (priority order):
  1. Photo card  — article image downloaded as full-bleed background with
                   gradient overlay + text (used when image_url is available)
  2. Text card   — pure branded text design (fallback when no photo)

Each page has its own visual identity:
  FinPulse   — Dark #050D0F + Teal  #00D4AA  (Bloomberg-style terminal)
  TechPulse  — Dark #0D1117 + Blue  #58A6FF  (GitHub-style dark)
  CorpPulse  — Dark #0F0F0F + Gold  #C9A84C  (Premium corporate)
  WorldPulse — Dark #0A1628 + Red   #E63946  (Breaking news)

Usage:
  python3 image.py                        # top article from DB
  python3 image.py --page techpulse
  python3 image.py --preview
  python3 image.py --article-id 42
"""

from __future__ import annotations

import io
import json
import os
import sys
import textwrap
import urllib.request
import urllib.error
from datetime import datetime
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance
except ImportError:
    print("❌ Pillow not installed. Run: pip3 install Pillow")
    sys.exit(1)

sys.path.insert(0, os.path.dirname(__file__))

SIZE = 1080

# ─────────────────────────────────────────────
# PAGE BRAND CONFIGS
# ─────────────────────────────────────────────

BRANDS = {
    "finpulse": {
        "name":       "FinPulse",
        "handle":     "@finpulse.daily",
        "tagline":    "MARKET INTELLIGENCE",
        "bg":         (5,  13,  15),
        "accent":     (0,  212, 170),
        "accent2":    (0,  150, 120),
        "text_main":  (255, 255, 255),
        "text_dim":   (160, 175, 185),
        "text_badge": (5,  13,  15),
        "bar_top":    (0,  212, 170),
        "bar_bot":    (0,  80,  65),
        "category_colors": {
            "markets": (0, 212, 170),
            "macro":   (0, 180, 230),
            "filing":  (255, 200, 0),
            "crypto":  (255, 150, 0),
            "":        (0, 212, 170),
        },
    },
    "techpulse": {
        "name":       "TechPulse",
        "handle":     "@techpulse.daily",
        "tagline":    "TECH INTELLIGENCE",
        "bg":         (13, 17, 23),
        "accent":     (88, 166, 255),
        "accent2":    (50, 100, 200),
        "text_main":  (255, 255, 255),
        "text_dim":   (139, 148, 158),
        "text_badge": (13, 17, 23),
        "bar_top":    (88, 166, 255),
        "bar_bot":    (30, 60, 120),
        "category_colors": {
            "tech": (88, 166, 255),
            "ai":   (180, 100, 255),
            "":     (88, 166, 255),
        },
    },
    "corppulse": {
        "name":       "CorpPulse",
        "handle":     "@corppulse.daily",
        "tagline":    "BUSINESS INTELLIGENCE",
        "bg":         (10, 10, 12),
        "accent":     (201, 168, 76),
        "accent2":    (140, 110, 40),
        "text_main":  (255, 255, 255),
        "text_dim":   (160, 155, 140),
        "text_badge": (10, 10, 12),
        "bar_top":    (201, 168, 76),
        "bar_bot":    (80,  65,  20),
        "category_colors": {
            "corporate": (201, 168, 76),
            "earnings":  (100, 220, 130),
            "":          (201, 168, 76),
        },
    },
    "worldpulse": {
        "name":       "WorldPulse",
        "handle":     "@worldpulse.daily",
        "tagline":    "GLOBAL INTELLIGENCE",
        "bg":         (10, 22, 40),
        "accent":     (230, 57, 70),
        "accent2":    (160, 30, 40),
        "text_main":  (255, 255, 255),
        "text_dim":   (150, 165, 185),
        "text_badge": (255, 255, 255),
        "bar_top":    (230, 57, 70),
        "bar_bot":    (80,  15, 20),
        "category_colors": {
            "world": (230, 57, 70),
            "":      (230, 57, 70),
        },
    },
}


# ─────────────────────────────────────────────
# FONT LOADER
# ─────────────────────────────────────────────

_FONT_SEARCH = {
    "bold": [
        "/System/Library/Fonts/HelveticaNeue.ttc",
        "/System/Library/Fonts/Helvetica.ttc",
        "/System/Library/Fonts/SFNSDisplay.ttf",
        "/Library/Fonts/Arial Bold.ttf",
        "/usr/share/fonts/truetype/google-fonts/Poppins-Bold.ttf",
        "/usr/share/fonts/truetype/lato/Lato-Black.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ],
    "semibold": [
        "/System/Library/Fonts/HelveticaNeue.ttc",
        "/System/Library/Fonts/Helvetica.ttc",
        "/usr/share/fonts/truetype/google-fonts/Poppins-Medium.ttf",
        "/usr/share/fonts/truetype/lato/Lato-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ],
    "regular": [
        "/System/Library/Fonts/HelveticaNeue.ttc",
        "/System/Library/Fonts/Helvetica.ttc",
        "/Library/Fonts/Arial.ttf",
        "/usr/share/fonts/truetype/google-fonts/Poppins-Regular.ttf",
        "/usr/share/fonts/truetype/lato/Lato-Regular.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ],
    "light": [
        "/System/Library/Fonts/HelveticaNeue.ttc",
        "/System/Library/Fonts/Helvetica.ttc",
        "/usr/share/fonts/truetype/google-fonts/Poppins-Light.ttf",
        "/usr/share/fonts/truetype/lato/Lato-Light.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ],
}

_font_cache: dict = {}

def _load_font(style: str = "regular", size: int = 40) -> ImageFont.FreeTypeFont:
    key = (style, size)
    if key in _font_cache:
        return _font_cache[key]
    for path in _FONT_SEARCH.get(style, _FONT_SEARCH["regular"]):
        if os.path.exists(path):
            try:
                font = ImageFont.truetype(path, size)
                _font_cache[key] = font
                return font
            except Exception:
                continue
    font = ImageFont.load_default()
    _font_cache[key] = font
    return font


# ─────────────────────────────────────────────
# TEXT UTILITIES
# ─────────────────────────────────────────────

def _wrap_text(draw, text: str, font, max_width: int) -> list[str]:
    words = text.split()
    lines, current = [], ""
    for word in words:
        test = (current + " " + word).strip()
        w = draw.textbbox((0, 0), test, font=font)[2]
        if w <= max_width:
            current = test
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines

def _auto_size_headline(draw, text: str, max_w: int, max_h: int,
                        size_start: int = 72, size_min: int = 36):
    for size in range(size_start, size_min - 1, -4):
        font = _load_font("bold", size)
        lines = _wrap_text(draw, text, font, max_w)
        line_h = draw.textbbox((0, 0), "Ag", font=font)[3] + 14
        if line_h * len(lines) <= max_h and len(lines) <= 5:
            return lines, font
    font = _load_font("bold", size_min)
    return _wrap_text(draw, text, font, max_w)[:5], font

def _text_w(draw, text, font):
    return draw.textbbox((0, 0), text, font=font)[2]

def _text_h(draw, text, font):
    return draw.textbbox((0, 0), text, font=font)[3]


# ─────────────────────────────────────────────
# DRAWING HELPERS
# ─────────────────────────────────────────────

def _rounded_rect(draw, xy, radius, fill):
    x1, y1, x2, y2 = xy
    draw.rectangle([x1+radius, y1, x2-radius, y2], fill=fill)
    draw.rectangle([x1, y1+radius, x2, y2-radius], fill=fill)
    for corner in [(x1,y1),(x2-2*radius,y1),(x1,y2-2*radius),(x2-2*radius,y2-2*radius)]:
        draw.ellipse([corner[0], corner[1], corner[0]+2*radius, corner[1]+2*radius], fill=fill)

def _alpha_rect(img, xy, color, alpha=40):
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    r, g, b = color
    d.rectangle(xy, fill=(r, g, b, alpha))
    img.paste(overlay, mask=overlay)


# ─────────────────────────────────────────────
# PHOTO DOWNLOAD HELPERS
# ─────────────────────────────────────────────

_HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}

def _try_download_image(url: str) -> Image.Image | None:
    """Download an image URL and return a PIL Image, or None on failure."""
    if not url or not url.startswith("http"):
        return None
    try:
        req = urllib.request.Request(url, headers=_HEADERS)
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = resp.read(8 * 1024 * 1024)  # 8 MB cap
        img = Image.open(io.BytesIO(data)).convert("RGB")
        # Must be at least 300×200 to be useful
        if img.width < 300 or img.height < 200:
            return None
        return img
    except Exception:
        return None


def _get_best_photo(article: dict) -> Image.Image | None:
    """Try all image URLs from the article until one downloads successfully."""
    candidates: list[str] = []

    primary = article.get("image_url") or ""
    if primary:
        candidates.append(primary)

    urls_raw = article.get("image_urls", [])
    if isinstance(urls_raw, str):
        try:
            urls_raw = json.loads(urls_raw)
        except Exception:
            urls_raw = []
    if isinstance(urls_raw, list):
        for u in urls_raw:
            if u and u not in candidates:
                candidates.append(u)

    for url in candidates[:6]:  # max 6 attempts
        photo = _try_download_image(url)
        if photo:
            print(f"  📷 Photo: {photo.width}×{photo.height}  {url[:60]}")
            return photo

    return None


def _crop_square(photo: Image.Image) -> Image.Image:
    """Center-crop to square, biased slightly upward (subjects tend to be higher)."""
    w, h = photo.size
    if w == h:
        return photo
    size = min(w, h)
    left = (w - size) // 2
    top  = max(0, (h - size) // 3)   # upper-third bias
    return photo.crop((left, top, left + size, top + size))


# ─────────────────────────────────────────────
# LAYOUT A: PHOTO CARD (primary)
# Full-bleed article photo + gradient overlay + branded text
# ─────────────────────────────────────────────

def _generate_with_photo(article: dict, page: str, brand: dict,
                          photo: Image.Image) -> Image.Image:
    # ── Prepare photo background ──────────────────────────────────────────────
    photo = _crop_square(photo).resize((SIZE, SIZE), Image.LANCZOS)
    # Slight desaturation so text pops
    photo = ImageEnhance.Color(photo).enhance(0.80)

    # ── Build vertical gradient overlay ──────────────────────────────────────
    # Top zone (brand header): semi-dark
    # Middle zone (photo showcase): minimal overlay — let the image breathe
    # Bottom zone (headline + footer): heavy dark
    bg_r, bg_g, bg_b = brand["bg"]
    overlay = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    d_ov = ImageDraw.Draw(overlay)

    for y in range(SIZE):
        p = y / SIZE
        if p < 0.18:
            a = 175                                          # header: solid-ish dark
        elif p < 0.42:
            t = (p - 0.18) / 0.24
            a = int(175 - t * 120)                          # fade out → 55
        elif p < 0.60:
            t = (p - 0.42) / 0.18
            a = int(55 + t * 45)                            # fade in → 100
        else:
            t = min(1.0, (p - 0.60) / 0.32)
            a = int(100 + t * 155)                          # ramp up → 255
            a = min(a, 252)
        d_ov.line([(0, y), (SIZE, y)], fill=(bg_r, bg_g, bg_b, a))

    img = Image.alpha_composite(photo.convert("RGBA"), overlay).convert("RGB")
    draw = ImageDraw.Draw(img)

    # ── TOP ACCENT BAR ────────────────────────────────────────────────────────
    draw.rectangle([0, 0, SIZE, 8], fill=brand["bar_top"])

    # ── HEADER: brand name + handle ───────────────────────────────────────────
    name_font   = _load_font("bold", 60)
    handle_font = _load_font("regular", 30)
    tag_font    = _load_font("light", 22)

    draw.text((52, 26), brand["name"], font=name_font, fill=brand["accent"])
    dot_x = 52 + _text_w(draw, brand["name"], name_font) + 18
    draw.ellipse([dot_x, 60, dot_x+10, 70], fill=brand["text_dim"])
    draw.text((dot_x+22, 54), brand["handle"], font=handle_font, fill=brand["text_dim"])
    draw.text((55, 104), brand["tagline"], font=tag_font, fill=brand["accent2"])

    # LIVE badge
    live_font = _load_font("bold", 22)
    live_text = "● LIVE"
    lw = _text_w(draw, live_text, live_font)
    _rounded_rect(draw, (SIZE-lw-72, 28, SIZE-44, 70), radius=10, fill=brand["accent"])
    draw.text((SIZE-lw-58, 36), live_text, font=live_font, fill=brand["text_badge"])

    # ── CATEGORY BADGE + SOURCE (y ≈ 680) ────────────────────────────────────
    CAT_Y = 690
    cat = (article.get("category") or "").lower()
    cat_label = cat.upper() if cat else page.upper().replace("PULSE", " PULSE")
    cat_color = brand["category_colors"].get(cat, brand["accent"])

    badge_font = _load_font("bold", 26)
    bw = _text_w(draw, cat_label, badge_font)
    _rounded_rect(draw, (52, CAT_Y, 52+bw+28, CAT_Y+42), radius=7, fill=cat_color)
    draw.text((66, CAT_Y+9), cat_label, font=badge_font, fill=brand["text_badge"])

    src_name = (article.get("source_name") or "")[:28]
    src_font = _load_font("regular", 24)
    sw = _text_w(draw, src_name, src_font)
    draw.text((SIZE-sw-52, CAT_Y+9), src_name, font=src_font, fill=brand["text_dim"])

    # ── HEADLINE (y ≈ 748 → up to 950) ───────────────────────────────────────
    HL_Y   = CAT_Y + 58
    HL_W   = SIZE - 104
    HL_H   = 250

    title = article.get("title", "")
    hl_lines, hl_font = _auto_size_headline(draw, title, HL_W, HL_H,
                                             size_start=68, size_min=36)
    lh = draw.textbbox((0, 0), "Ag", font=hl_font)[3] + 14
    total_hl_h = lh * len(hl_lines)

    # Accent left bar
    draw.rectangle([28, HL_Y-4, 42, HL_Y+total_hl_h+4], fill=brand["accent"])
    for i, line in enumerate(hl_lines):
        draw.text((54, HL_Y + i*lh), line, font=hl_font, fill=brand["text_main"])

    # ── FOOTER ────────────────────────────────────────────────────────────────
    FOOT_Y = 978
    draw.rectangle([52, FOOT_Y-3, SIZE-52, FOOT_Y], fill=brand["accent2"])

    pub = article.get("published_at", "")
    try:
        date_str = datetime.fromisoformat(pub).strftime("%b %d, %Y  %H:%M UTC")
    except Exception:
        date_str = datetime.utcnow().strftime("%b %d, %Y")

    meta_font = _load_font("light", 24)
    draw.text((52, FOOT_Y+8), date_str, font=meta_font, fill=brand["text_dim"])

    score = article.get("score", 0)
    if score:
        sc_str = f"Score: {score:.0f}pt"
        draw.text((SIZE-_text_w(draw, sc_str, meta_font)-52, FOOT_Y+8),
                  sc_str, font=meta_font, fill=brand["accent"])

    # Bottom accent bar
    draw.rectangle([0, SIZE-8, SIZE, SIZE], fill=brand["bar_top"])

    return img


# ─────────────────────────────────────────────
# LAYOUT B: TEXT CARD (fallback)
# Pure branded design — no photo needed
# ─────────────────────────────────────────────

def _generate_text_only(article: dict, page: str, brand: dict) -> Image.Image:
    img  = Image.new("RGB", (SIZE, SIZE), color=brand["bg"])
    draw = ImageDraw.Draw(img)

    # Dot-grid texture
    dot_color = tuple(min(c+18, 255) for c in brand["bg"])
    for gx in range(0, SIZE, 40):
        for gy in range(0, SIZE, 40):
            draw.ellipse([gx-1, gy-1, gx+1, gy+1], fill=dot_color)

    _alpha_rect(img, (0, 250, SIZE, 830), brand["accent"], alpha=8)

    draw.rectangle([0, 0, SIZE, 8], fill=brand["bar_top"])

    # Header
    HEADER_H  = 192
    name_font = _load_font("bold", 64)
    draw.text((52, 32), brand["name"], font=name_font, fill=brand["accent"])
    dot_x = 52 + _text_w(draw, brand["name"], name_font) + 18
    draw.ellipse([dot_x, 68, dot_x+10, 78], fill=brand["text_dim"])
    draw.text((dot_x+22, 62), brand["handle"],
              font=_load_font("regular", 32), fill=brand["text_dim"])
    draw.text((55, 112), brand["tagline"],
              font=_load_font("light", 24), fill=brand["accent2"])

    # LIVE badge
    live_font = _load_font("bold", 24)
    live_text = "● LIVE"
    lw = _text_w(draw, live_text, live_font)
    _rounded_rect(draw, (SIZE-lw-80, 34, SIZE-44, 80), radius=12, fill=brand["accent"])
    draw.text((SIZE-lw-64, 44), live_text, font=live_font, fill=brand["text_badge"])

    draw.rectangle([52, HEADER_H-4, SIZE-52, HEADER_H], fill=brand["accent2"])

    # Category badge
    cat = (article.get("category") or "").lower()
    cat_label = cat.upper() if cat else page.upper().replace("PULSE", " PULSE")
    cat_color = brand["category_colors"].get(cat, brand["accent"])
    badge_font = _load_font("bold", 26)
    bw = _text_w(draw, cat_label, badge_font)
    bx, by = 52, HEADER_H+28
    _rounded_rect(draw, (bx, by, bx+bw+32, by+46), radius=8, fill=cat_color)
    draw.text((bx+16, by+10), cat_label, font=badge_font, fill=brand["text_badge"])

    src_name = (article.get("source_name") or "")[:30]
    src_font = _load_font("regular", 26)
    sw = _text_w(draw, src_name, src_font)
    draw.text((SIZE-sw-52, by+10), src_name, font=src_font, fill=brand["text_dim"])

    # Headline
    HL_Y_START = HEADER_H + 100
    title = article.get("title", "")
    hl_lines, hl_font = _auto_size_headline(draw, title, SIZE-104, 400,
                                             size_start=76, size_min=40)
    lh = draw.textbbox((0, 0), "Ag", font=hl_font)[3] + 14
    total_hl_h = lh * len(hl_lines)
    draw.rectangle([28, HL_Y_START-4, 40, HL_Y_START+total_hl_h+4], fill=brand["accent"])
    for i, line in enumerate(hl_lines):
        draw.text((52, HL_Y_START+i*lh), line, font=hl_font, fill=brand["text_main"])

    # Summary
    SUMMARY_Y = HL_Y_START + total_hl_h + 32
    summary_raw = (article.get("summary") or "").strip()
    if summary_raw:
        first = summary_raw.split(".")[0].strip()
        if len(first) < 40:
            first = summary_raw[:140]
        sum_font = _load_font("regular", 32)
        sum_lines = _wrap_text(draw, first[:160], sum_font, SIZE-104)
        slh = draw.textbbox((0, 0), "Ag", font=sum_font)[3] + 10
        for i, line in enumerate(sum_lines[:2]):
            draw.text((52, SUMMARY_Y+i*slh), line, font=sum_font, fill=brand["text_dim"])

    # Footer
    BOT_Y = 870
    draw.rectangle([52, BOT_Y, SIZE-52, BOT_Y+3], fill=brand["accent2"])
    pub = article.get("published_at", "")
    try:
        date_str = datetime.fromisoformat(pub).strftime("%b %d, %Y  %H:%M UTC")
    except Exception:
        date_str = datetime.utcnow().strftime("%b %d, %Y")
    meta_font = _load_font("light", 26)
    draw.text((52, BOT_Y+20), date_str, font=meta_font, fill=brand["text_dim"])
    score = article.get("score", 0)
    if score:
        sc_str = f"Score: {score:.0f}pt"
        draw.text((SIZE-_text_w(draw, sc_str, meta_font)-52, BOT_Y+20),
                  sc_str, font=meta_font, fill=brand["accent"])

    draw.rectangle([0, SIZE-8, SIZE, SIZE], fill=brand["bar_top"])

    # Logo mark
    for i in range(3):
        for j in range(3):
            cx, cy = SIZE-52-j*16, SIZE-44+i*0-40+j*12
            r = brand["accent"] if (i+j)%2==0 else brand["accent2"]
            draw.ellipse([cx-3, cy-3, cx+3, cy+3], fill=r)

    return img


# ─────────────────────────────────────────────
# PUBLIC API
# ─────────────────────────────────────────────

def generate_image(article: dict, page: str) -> str:
    """
    Generate a branded 1080×1080 PNG for the article.

    Uses the article's photo (image_url / image_urls) as a full-bleed
    background with a gradient overlay when one is available.
    Falls back to a pure text card if no usable photo is found.

    Returns the path to the saved PNG.
    """
    brand = BRANDS.get(page, BRANDS["finpulse"])

    print(f"  🔍 Looking for article photo…")
    photo = _get_best_photo(article)

    if photo:
        print(f"  🖼  Generating photo card")
        result_img = _generate_with_photo(article, page, brand, photo)
    else:
        print(f"  📝 No photo found — using text-only design")
        result_img = _generate_text_only(article, page, brand)

    # ── Save ──────────────────────────────────────────────────────────────────
    out_dir = os.path.join(os.path.dirname(__file__), "output", "images")
    os.makedirs(out_dir, exist_ok=True)

    article_id = article.get("id", 0)
    ts         = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    filename   = f"{page}_{article_id}_{ts}.png"
    path       = os.path.join(out_dir, filename)

    result_img.save(path, "PNG", optimize=True)
    print(f"  ✅ Saved: output/images/{filename}")
    return path


# ─────────────────────────────────────────────
# SAVE PATH TO DB
# ─────────────────────────────────────────────

def save_image_path(article_id: int, image_path: str, page: str):
    try:
        from database.schema import get_connection
        conn = get_connection()
        conn.execute(
            "UPDATE posts SET image_path=? WHERE article_id=? AND page=?",
            (image_path, article_id, page)
        )
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"  ⚠️  DB update skipped: {e}")


# ─────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────

def main():
    page       = "finpulse"
    preview    = False
    article_id = None

    for arg in sys.argv[1:]:
        if arg == "--preview":                preview    = True
        elif arg.startswith("--page="):       page       = arg.split("=")[1]
        elif arg.startswith("--article-id="): article_id = int(arg.split("=")[1])
        elif arg in ("finpulse","techpulse","corppulse","worldpulse"): page = arg

    from database.models import get_top_articles
    from database.schema  import get_connection

    if article_id:
        conn = get_connection()
        row  = conn.execute("SELECT * FROM articles WHERE id=?", (article_id,)).fetchone()
        conn.close()
        if not row:
            print(f"❌ Article ID {article_id} not found"); return
        article = dict(row)
    else:
        articles = get_top_articles(page, limit=1)
        if not articles:
            print(f"❌ No articles for {page}"); return
        article = articles[0]

    print(f"\n{'='*60}")
    print(f"🎨 IMAGE GENERATOR — {page.upper()}")
    print(f"{'='*60}")
    print(f"📰 {article['title'][:70]}")
    print(f"   Source: {article.get('source_name','')}  |  Score: {article.get('score',0)}pts")
    print(f"   Photo URL: {(article.get('image_url') or 'none')[:80]}\n")

    path = generate_image(article, page)

    if not preview:
        save_image_path(article.get("id", 0), path, page)
        print(f"\n✅ Done → {path}")
        print(f"   Next: python3 instagram.py to post")
    else:
        print(f"\n👁  Preview — opening image…")
        try:
            import subprocess
            subprocess.run(["open", path], check=False, timeout=3)
        except Exception:
            pass


if __name__ == "__main__":
    main()
