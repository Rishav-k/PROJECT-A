"""
carousel.py — Pulse Media Analysis Carousel Generator
Creates 5-slide 1080×1080 Instagram carousel posts with full news analysis.

Slide structure:
  1. HERO        — article photo (or branded text card) + headline
  2. WHAT HAPPENED — summary / story context
  3. PROS + WHO BENEFITS — winners and upsides
  4. CONS + WHO LOSES    — risks and who gets hurt
  5. BOTTOM LINE + CTA   — key takeaway + follow prompt

Usage:
    from carousel import generate_carousel
    paths = generate_carousel(article_dict, page="finpulse",
                              caption="...", caption_data={...})
    # returns list of 5 Path objects (JPEG, 1080×1080, ready for album_upload)
"""

from __future__ import annotations

import io
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

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

# ── Page themes ───────────────────────────────────────────────────────────────
THEMES = {
    "finpulse": {
        "name":    "FinPulse",
        "handle":  "@finpulse.daily",
        "tagline": "MARKET INTELLIGENCE",
        "accent":  (0, 212, 170),
        "accent2": (0, 120, 100),
        "bg":      (5,  13,  15),
        "text":    (255, 255, 255),
        "muted":   (140, 160, 170),
    },
    "techpulse": {
        "name":    "TechPulse",
        "handle":  "@techpulse.daily",
        "tagline": "TECH INTELLIGENCE",
        "accent":  (88, 166, 255),
        "accent2": (40,  90, 180),
        "bg":      (13,  17,  23),
        "text":    (255, 255, 255),
        "muted":   (120, 140, 160),
    },
    "corppulse": {
        "name":    "CorpPulse",
        "handle":  "@corppulse.daily",
        "tagline": "BUSINESS INTELLIGENCE",
        "accent":  (201, 168, 76),
        "accent2": (110,  90, 30),
        "bg":      (10,  10,  12),
        "text":    (255, 255, 255),
        "muted":   (150, 140, 120),
    },
    "worldpulse": {
        "name":    "WorldPulse",
        "handle":  "@worldpulse.daily",
        "tagline": "GLOBAL INTELLIGENCE",
        "accent":  (230, 57,  70),
        "accent2": (130, 20,  30),
        "bg":      (10,  22,  40),
        "text":    (255, 255, 255),
        "muted":   (130, 150, 180),
    },
}

GREEN  = (40,  200, 100)
GREEN2 = (20,  120,  60)
RED    = (220,  50,  60)
RED2   = (130,  20,  30)


# ── Font loader ───────────────────────────────────────────────────────────────
_FONTS = {
    "bold":    ["/System/Library/Fonts/HelveticaNeue.ttc",
                "/System/Library/Fonts/Helvetica.ttc",
                "/Library/Fonts/Arial Bold.ttf",
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"],
    "regular": ["/System/Library/Fonts/HelveticaNeue.ttc",
                "/System/Library/Fonts/Helvetica.ttc",
                "/Library/Fonts/Arial.ttf",
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"],
    "light":   ["/System/Library/Fonts/HelveticaNeue.ttc",
                "/System/Library/Fonts/Helvetica.ttc",
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"],
}
_font_cache: dict = {}

def _font(style: str = "regular", size: int = 36) -> ImageFont.FreeTypeFont:
    k = (style, size)
    if k in _font_cache: return _font_cache[k]
    for p in _FONTS.get(style, _FONTS["regular"]):
        if os.path.exists(p):
            try:
                f = ImageFont.truetype(p, size); _font_cache[k] = f; return f
            except Exception: pass
    f = ImageFont.load_default(); _font_cache[k] = f; return f


# ── Drawing helpers ───────────────────────────────────────────────────────────

def _tw(d: ImageDraw.ImageDraw, text, font) -> int:
    return d.textbbox((0, 0), text, font=font)[2]

def _th(d: ImageDraw.ImageDraw, text, font) -> int:
    return d.textbbox((0, 0), text, font=font)[3]

def _wrap(d: ImageDraw.ImageDraw, text: str, font, max_w: int) -> list[str]:
    words = text.split(); lines = []; cur = ""
    for w in words:
        t = (cur + " " + w).strip()
        if _tw(d, t, font) <= max_w: cur = t
        else:
            if cur: lines.append(cur)
            cur = w
    if cur: lines.append(cur)
    return lines

def _draw_wrapped(d: ImageDraw.ImageDraw, text: str, font, max_w: int,
                  x: int, y: int, fill: tuple, spacing: int = 10,
                  max_lines: int = 99) -> int:
    lines = _wrap(d, text, font, max_w)[:max_lines]
    lh = _th(d, "Ag", font) + spacing
    for line in lines:
        d.text((x, y), line, font=font, fill=fill); y += lh
    return y

def _rounded_rect(d: ImageDraw.ImageDraw, xy, r, fill):
    x1, y1, x2, y2 = xy
    d.rectangle([x1+r, y1, x2-r, y2], fill=fill)
    d.rectangle([x1, y1+r, x2, y2-r], fill=fill)
    for c in [(x1,y1),(x2-2*r,y1),(x1,y2-2*r),(x2-2*r,y2-2*r)]:
        d.ellipse([c[0],c[1],c[0]+2*r,c[1]+2*r], fill=fill)

def _dark_bg(img: Image.Image, accent: tuple):
    """Draw subtle radial tint on solid dark background."""
    d = ImageDraw.Draw(img)
    ar, ag, ab = accent
    for i in range(0, 280, 4):
        a = int(18 * (1 - i / 280))
        d.ellipse([-150+i, -150+i, 450-i, 450-i],
                  outline=(min(ar,100), min(ag,100), min(ab,100)))

def _brand_footer(d: ImageDraw.ImageDraw, theme: dict, slide_n: int, total: int):
    """Bottom brand bar: dot · name · handle  and page number."""
    ax, ay = 60, SIZE - 60
    accent = theme["accent"]
    d.ellipse([ax, ay-8, ax+12, ay+4], fill=accent)
    fn = _font("bold",   26)
    fh = _font("regular", 22)
    d.text((ax+20, ay-10), theme["name"],   font=fn, fill=accent)
    d.text((ax+20, ay+18), theme["handle"], font=fh, fill=theme["muted"])
    # page number right
    pg = f"{slide_n}/{total}"
    fw = _font("regular", 22)
    d.text((SIZE - _tw(d, pg, fw) - 52, SIZE - 52), pg, font=fw, fill=theme["muted"])

def _swipe_indicator(d: ImageDraw.ImageDraw, accent: tuple):
    fsw = _font("bold", 28)
    txt = "SWIPE  →"
    d.text((SIZE - _tw(d, txt, fsw) - 56, SIZE - 100), txt, font=fsw, fill=accent)

def _top_bar(img: Image.Image, accent: tuple):
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, SIZE, 8], fill=accent)
    d.rectangle([0, SIZE-8, SIZE, SIZE], fill=accent)

def _save(img: Image.Image, page: str, article_id: int, slide_n: int) -> Path:
    ts  = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = OUTPUT_DIR / f"{page}_c{article_id}_s{slide_n}_{ts}.jpg"
    img.save(str(out), "JPEG", quality=92, optimize=False, progressive=False, subsampling=0)
    return out


# ══════════════════════════════════════════════════════════════════════════════
# SLIDE 1 — HERO  (article photo or branded text card)
# ══════════════════════════════════════════════════════════════════════════════

def _slide1_hero(article: dict, theme: dict, art_id: int) -> Path:
    """
    Use the article's photo as a full-bleed background.
    Falls back to a text-only branded card.
    Also overlays slide indicators and SWIPE prompt.
    """
    try:
        # Re-use image.py's photo download + layout logic
        from image import _get_best_photo, _crop_square, _generate_with_photo, _generate_text_only, BRANDS
        brand = BRANDS.get(article.get("page", "finpulse"), BRANDS["finpulse"])
        photo = _get_best_photo(article)
        if photo:
            base = _generate_with_photo(article, article.get("page","finpulse"), brand, photo)
        else:
            base = _generate_text_only(article, article.get("page","finpulse"), brand)
    except Exception as e:
        print(f"  ⚠️  image.py import failed ({e}), drawing fallback slide 1")
        base = Image.new("RGB", (SIZE, SIZE), theme["bg"])
        d = ImageDraw.Draw(base)
        _dark_bg(base, theme["accent"])
        d.rectangle([0, 0, SIZE, 8], fill=theme["accent"])
        title = article.get("title", "")
        _draw_wrapped(d, title, _font("bold", 62), SIZE-104, 52, 200,
                      theme["text"], spacing=14)
        d.rectangle([0, SIZE-8, SIZE, SIZE], fill=theme["accent"])

    # Overlay slide counter badge (top-right)
    d = ImageDraw.Draw(base)
    badge_font = _font("bold", 26)
    badge_txt  = "1 / 5"
    bw = _tw(d, badge_txt, badge_font) + 24
    _rounded_rect(d, (SIZE-bw-40, 20, SIZE-40, 60), r=10,
                  fill=(*theme["accent"], 200) if len(theme["accent"])==3
                  else theme["accent"])
    d.text((SIZE-bw-28, 28), badge_txt, font=badge_font, fill=(10,10,15))

    # "SWIPE for analysis →"
    sw_font = _font("bold", 26)
    sw_txt  = "SWIPE for analysis  →"
    sw_x    = SIZE - _tw(d, sw_txt, sw_font) - 56
    # Semi-dark pill behind text
    _rounded_rect(d, (sw_x-12, SIZE-98, SIZE-40, SIZE-62), r=8, fill=(0,0,0,160))
    d.text((sw_x, SIZE-94), sw_txt, font=sw_font, fill=theme["accent"])

    return _save(base, article.get("page","finpulse"), art_id, 1)


# ══════════════════════════════════════════════════════════════════════════════
# SLIDE 2 — WHAT HAPPENED
# ══════════════════════════════════════════════════════════════════════════════

def _slide2_what_happened(article: dict, theme: dict, art_id: int,
                           summary: str = "") -> Path:
    img = Image.new("RGB", (SIZE, SIZE), theme["bg"])
    _dark_bg(img, theme["accent"])
    _top_bar(img, theme["accent"])
    d = ImageDraw.Draw(img)

    # Section label
    lbl = _font("bold", 30)
    d.text((60, 38), "WHAT HAPPENED", font=lbl, fill=theme["accent"])
    d.rectangle([60, 82, SIZE//2, 86], fill=theme["accent"])

    # Large decorative quote
    fq = _font("bold", 180)
    d.text((820, 30), "“", font=fq, fill=(*theme["accent"], 25))

    # Summary body
    if not summary:
        summary = article.get("summary", "") or article.get("title", "")
    body_font = _font("regular", 44)
    _draw_wrapped(d, summary[:400], body_font, SIZE-120, 60, 160,
                  (235, 240, 245), spacing=18, max_lines=10)

    # Source + date footer stripe
    d.rectangle([60, 870, SIZE-60, 873], fill=theme["accent2"])
    src_font = _font("regular", 26)
    d.text((60, 882), article.get("source_name", ""), font=src_font, fill=theme["muted"])
    pub = article.get("published_at", "")
    try:
        ds = datetime.fromisoformat(pub).strftime("%b %d, %Y")
    except Exception:
        ds = datetime.utcnow().strftime("%b %d, %Y")
    d.text((SIZE-_tw(d, ds, src_font)-60, 882), ds, font=src_font, fill=theme["muted"])

    _swipe_indicator(d, theme["accent"])
    _brand_footer(d, theme, 2, 5)
    return _save(img, article.get("page","finpulse"), art_id, 2)


# ══════════════════════════════════════════════════════════════════════════════
# SLIDE 3 — PROS + WHO BENEFITS
# ══════════════════════════════════════════════════════════════════════════════

def _slide3_pros(article: dict, theme: dict, art_id: int,
                 pros: list, who_benefits: list) -> Path:
    img = Image.new("RGB", (SIZE, SIZE), theme["bg"])
    _dark_bg(img, GREEN)
    _top_bar(img, GREEN)
    d = ImageDraw.Draw(img)

    # Header
    lbl = _font("bold", 30)
    d.text((60, 38), "PROS  &  WHO BENEFITS", font=lbl, fill=GREEN)
    d.rectangle([60, 82, 680, 86], fill=GREEN)

    # Check icon watermark
    fw = _font("bold", 200)
    d.text((800, -10), "✓", font=fw, fill=(*GREEN, 18))

    y = 130

    # PROS section
    if pros:
        sec_f = _font("bold", 26)
        d.text((60, y), "UPSIDES", font=sec_f, fill=GREEN)
        y += 38
        for pt in pros[:3]:
            # Green pill badge "✓"
            _rounded_rect(d, (60, y+2, 98, y+40), r=8, fill=GREEN)
            d.text((69, y+6), "✓", font=_font("bold", 24), fill=(10,10,15))
            body_f = _font("regular", 38)
            ny = _draw_wrapped(d, pt, body_f, SIZE-150, 110, y,
                               (235,245,240), spacing=10, max_lines=2)
            y = max(ny, y + 50) + 12

    y += 20

    # WHO BENEFITS section
    if who_benefits:
        sec_f = _font("bold", 26)
        d.text((60, y), "WHO BENEFITS", font=sec_f, fill=GREEN)
        y += 38
        for grp in who_benefits[:3]:
            _rounded_rect(d, (60, y+6, 40+_tw(d, "★", _font("bold",24))+40, y+42), r=8,
                          fill=(20, 80, 50))
            d.text((69, y+10), "★", font=_font("bold", 22), fill=GREEN)
            body_f = _font("regular", 36)
            ny = _draw_wrapped(d, grp, body_f, SIZE-150, 110, y,
                               (220, 240, 230), spacing=8, max_lines=2)
            y = max(ny, y + 46) + 10

    _swipe_indicator(d, GREEN)
    _brand_footer(d, theme, 3, 5)
    return _save(img, article.get("page","finpulse"), art_id, 3)


# ══════════════════════════════════════════════════════════════════════════════
# SLIDE 4 — CONS + WHO LOSES
# ══════════════════════════════════════════════════════════════════════════════

def _slide4_cons(article: dict, theme: dict, art_id: int,
                 cons: list, who_loses: list) -> Path:
    img = Image.new("RGB", (SIZE, SIZE), theme["bg"])
    _dark_bg(img, RED)
    _top_bar(img, RED)
    d = ImageDraw.Draw(img)

    # Header
    lbl = _font("bold", 30)
    d.text((60, 38), "CONS  &  WHO LOSES", font=lbl, fill=RED)
    d.rectangle([60, 82, 620, 86], fill=RED)

    # Warning watermark
    fw = _font("bold", 200)
    d.text((800, -10), "✗", font=fw, fill=(*RED, 18))

    y = 130

    # CONS section
    if cons:
        sec_f = _font("bold", 26)
        d.text((60, y), "RISKS & DOWNSIDES", font=sec_f, fill=RED)
        y += 38
        for pt in cons[:3]:
            _rounded_rect(d, (60, y+2, 98, y+40), r=8, fill=RED)
            d.text((69, y+8), "✗", font=_font("bold", 24), fill=(10,10,15))
            body_f = _font("regular", 38)
            ny = _draw_wrapped(d, pt, body_f, SIZE-150, 110, y,
                               (245, 230, 230), spacing=10, max_lines=2)
            y = max(ny, y + 50) + 12

    y += 20

    # WHO LOSES section
    if who_loses:
        sec_f = _font("bold", 26)
        d.text((60, y), "WHO GETS HURT", font=sec_f, fill=RED)
        y += 38
        for grp in who_loses[:3]:
            _rounded_rect(d, (60, y+6, 98, y+42), r=8, fill=(80, 20, 20))
            d.text((69, y+10), "▼", font=_font("bold", 22), fill=RED)
            body_f = _font("regular", 36)
            ny = _draw_wrapped(d, grp, body_f, SIZE-150, 110, y,
                               (240, 215, 215), spacing=8, max_lines=2)
            y = max(ny, y + 46) + 10

    _swipe_indicator(d, RED)
    _brand_footer(d, theme, 4, 5)
    return _save(img, article.get("page","finpulse"), art_id, 4)


# ══════════════════════════════════════════════════════════════════════════════
# SLIDE 5 — BOTTOM LINE + CTA
# ══════════════════════════════════════════════════════════════════════════════

def _slide5_cta(article: dict, theme: dict, art_id: int,
                takeaway: str = "", cta: str = "") -> Path:
    img = Image.new("RGB", (SIZE, SIZE), theme["bg"])
    _dark_bg(img, theme["accent"])
    _top_bar(img, theme["accent"])
    d = ImageDraw.Draw(img)

    accent = theme["accent"]

    # Section label
    lbl = _font("bold", 30)
    d.text((60, 38), "BOTTOM LINE", font=lbl, fill=accent)
    d.rectangle([60, 82, 380, 86], fill=accent)

    # Large quote mark
    fq = _font("bold", 160)
    d.text((40, 90), "“", font=fq, fill=(*accent, 55))

    # Takeaway big quote text
    tk_font = _font("bold", 52)
    _draw_wrapped(d, takeaway or article.get("title", "")[:160], tk_font,
                  SIZE-120, 60, 220, (255,255,255), spacing=16, max_lines=6)

    # Divider
    d.rectangle([60, 720, SIZE-60, 723], fill=theme["accent2"])

    # CTA
    if cta:
        cta_font = _font("regular", 36)
        _draw_wrapped(d, "💬 " + cta, cta_font, SIZE-120, 60, 740,
                      (210, 220, 230), spacing=12, max_lines=3)

    # Follow pill button
    btn_y = 870
    btn_txt = f"FOLLOW  {theme['handle']}"
    btn_f   = _font("bold", 32)
    bw      = _tw(d, btn_txt, btn_f) + 60
    bx      = (SIZE - bw) // 2
    _rounded_rect(d, (bx, btn_y, bx+bw, btn_y+62), r=31, fill=accent)
    d.text((bx + 30, btn_y + 14), btn_txt, font=btn_f, fill=(10,10,15))

    # Tagline
    tag_f = _font("light", 26)
    tag   = "Turn on notifications. Never miss a move."
    d.text(((SIZE - _tw(d, tag, tag_f)) // 2, btn_y + 80),
           tag, font=tag_f, fill=theme["muted"])

    _brand_footer(d, theme, 5, 5)
    return _save(img, article.get("page","finpulse"), art_id, 5)


# ══════════════════════════════════════════════════════════════════════════════
# CAPTION PARSER
# ══════════════════════════════════════════════════════════════════════════════

def _parse_caption(caption: str, title: str) -> dict:
    """
    Extract structured analysis data from a caption string.
    Handles sections from ai.py: PROS, CONS, WHO BENEFITS, WHO LOSES, CTA.
    """
    def extract(label, stops):
        pattern = rf"{label}:?\s*\n?(.*?)(?={'|'.join(stops)}|\Z)"
        m = re.search(pattern, caption, re.IGNORECASE | re.DOTALL)
        return m.group(1).strip() if m else ""

    def bullets(s, max_n=3):
        lines = [l.strip().lstrip("•✅❌▼★✓✗-*1234567890.).").strip()
                 for l in s.splitlines() if l.strip()]
        return [l for l in lines if len(l) > 5][:max_n]

    summary_raw  = extract("ANALYSIS",     ["PROS","CONS","WHO","CTA","HASHTAGS"])
    pros_raw     = extract("PROS",         ["CONS","WHO BENEFITS","WHO LOSES","CTA","HASHTAGS"])
    cons_raw     = extract("CONS",         ["WHO BENEFITS","WHO LOSES","CTA","HASHTAGS"])
    benefits_raw = extract("WHO BENEFITS", ["WHO LOSES","CTA","HASHTAGS"])
    losers_raw   = extract("WHO LOSES",    ["CTA","HASHTAGS"])
    cta_raw      = extract("CTA",          ["HASHTAGS"])
    takeaway_raw = extract("BOTTOM LINE",  ["CTA","HASHTAGS"])

    # Summary: use ANALYSIS section, or first long non-hashtag line
    summary = summary_raw.strip()
    if not summary:
        for line in caption.splitlines():
            clean = re.sub(r"[^\w\s.,!?'\"-]", "", line).strip()
            if len(clean) > 40 and not line.strip().startswith("#"):
                summary = clean
                break
    if not summary:
        summary = title

    # Takeaway: use BOTTOM LINE section or last long non-hashtag line
    takeaway = takeaway_raw.strip()
    if not takeaway:
        for line in reversed(caption.splitlines()):
            clean = re.sub(r"[^\w\s.,!?'\"-]", "", line).strip()
            if len(clean) > 30 and not line.strip().startswith("#"):
                takeaway = clean
                break
    if not takeaway or takeaway == summary:
        takeaway = title

    # Fallback bullet lists
    pros         = bullets(pros_raw) or ["Positive market developments expected",
                                          "New opportunities may emerge for investors",
                                          "Broader economic conditions may improve"]
    cons         = bullets(cons_raw) or ["Uncertainty remains in the short term",
                                          "Some sectors may face headwinds",
                                          "More clarity needed before acting"]
    who_benefits = bullets(benefits_raw) or ["Investors already positioned early",
                                              "Companies in adjacent sectors",
                                              "Policy makers and regulators"]
    who_loses    = bullets(losers_raw) or ["Short-sellers caught off-guard",
                                            "Competing firms in affected sectors",
                                            "Consumers facing price pressure"]
    cta          = cta_raw.strip() or "What's your take? Drop your thoughts below 👇"

    return {
        "summary":      summary[:350],
        "pros":         [p[:160] for p in pros],
        "cons":         [c[:160] for c in cons],
        "who_benefits": [b[:160] for b in who_benefits],
        "who_loses":    [l[:160] for l in who_loses],
        "takeaway":     takeaway[:220],
        "cta":          cta[:200],
    }


# ══════════════════════════════════════════════════════════════════════════════
# MAIN ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════

def generate_carousel(article: dict, page: str = "finpulse",
                      caption: str = "",
                      caption_data: dict | None = None) -> list:
    """
    Generate 5 analysis carousel slides.

    Args:
        article:      dict with id, title, source_name, score, page, etc.
        page:         finpulse / techpulse / corppulse / worldpulse
        caption:      raw caption string (parsed for structured data)
        caption_data: optional pre-parsed dict with keys pros, cons,
                      who_benefits, who_loses, cta (from ai.generate_caption)

    Returns:
        List of 5 Path objects (JPEG 1080×1080, ready for album_upload)
    """
    theme  = THEMES.get(page, THEMES["finpulse"])
    art_id = article.get("id", 0)

    # Get structured analysis — prefer caption_data, fallback to parsing caption
    if caption_data and isinstance(caption_data, dict):
        cd = caption_data
        summary      = (cd.get("analysis") or cd.get("summary") or "")[:350] or \
                       article.get("summary", "")[:350] or article.get("title", "")
        pros         = cd.get("pros", [])
        cons         = cd.get("cons", [])
        who_benefits = cd.get("who_benefits", [])
        who_loses    = cd.get("who_loses", [])
        cta          = cd.get("cta", "")
        takeaway     = (cd.get("hook") or cd.get("takeaway") or article.get("title",""))[:220]
    else:
        cd = _parse_caption(caption, article.get("title", ""))
        summary      = cd["summary"]
        pros         = cd["pros"]
        cons         = cd["cons"]
        who_benefits = cd["who_benefits"]
        who_loses    = cd["who_loses"]
        cta          = cd["cta"]
        takeaway     = cd["takeaway"]

    # Fill missing lists with fallbacks
    def _fill(lst, defaults):
        return lst if lst else defaults

    pros         = _fill(pros, ["Positive market developments expected",
                                  "New opportunities emerging",
                                  "Macro conditions favor this outcome"])
    cons         = _fill(cons, ["Short-term uncertainty remains",
                                  "Some sectors face headwinds",
                                  "Risk of overreaction in markets"])
    who_benefits = _fill(who_benefits, ["Early-positioned investors",
                                          "Adjacent sector companies",
                                          "Policy beneficiaries"])
    who_loses    = _fill(who_loses,    ["Short-sellers caught off-guard",
                                          "Competing firms in sector",
                                          "Consumers facing price changes"])

    print(f"  🎠 Generating {page} carousel for article {art_id}…")

    paths = [
        _slide1_hero(article, theme, art_id),
        _slide2_what_happened(article, theme, art_id, summary=summary),
        _slide3_pros(article, theme, art_id, pros=pros, who_benefits=who_benefits),
        _slide4_cons(article, theme, art_id, cons=cons, who_loses=who_loses),
        _slide5_cta(article, theme, art_id, takeaway=takeaway, cta=cta),
    ]

    for i, p in enumerate(paths, 1):
        sz = p.stat().st_size // 1024
        print(f"     Slide {i}: {p.name} ({sz}KB)")

    return paths


# ── Quick test ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    test_article = {
        "id": 1,
        "title": "Fed Holds Rates Steady as Inflation Shows Signs of Cooling",
        "source_name": "Reuters",
        "score": 88.0,
        "page": "finpulse",
        "url": "https://reuters.com/",
        "summary": "The Federal Reserve held interest rates steady for the third consecutive meeting "
                   "as policymakers noted that inflation is gradually moving back toward its 2% target. "
                   "Chair Jerome Powell signaled that cuts could come in late 2025 if data cooperates.",
        "published_at": datetime.utcnow().isoformat(),
        "image_url": "",
        "image_urls": "[]",
    }
    test_caption = (
        "🚨 BREAKING: Fed holds rates — here's what it means\n\n"
        "ANALYSIS:\n"
        "The Federal Reserve voted unanimously to hold rates at 5.25–5.5% today. "
        "Inflation at 2.9% is trending down but still above target. "
        "Markets are pricing in two cuts before year-end.\n\n"
        "PROS:\n"
        "• Mortgage rates may start to ease for homebuyers\n"
        "• Equity market valuations get a boost from lower discount rates\n"
        "• Small businesses see relief from high borrowing costs\n\n"
        "CONS:\n"
        "• Savers lose high-yield savings account rates\n"
        "• Dollar may weaken against major currencies\n"
        "• Banks face margin compression on loan portfolios\n\n"
        "WHO BENEFITS:\n"
        "• Homebuyers and real estate investors\n"
        "• Growth stocks and tech sector\n"
        "• Emerging market economies with dollar-denominated debt\n\n"
        "WHO LOSES:\n"
        "• Retirees dependent on fixed income\n"
        "• Banks and insurance companies\n"
        "• Forex traders long on the dollar\n\n"
        "CTA: Are you buying the dip or waiting for more clarity? Drop a comment 👇\n\n"
        "#FederalReserve #InterestRates #Investing #StockMarket #Fed"
    )
    paths = generate_carousel(test_article, page="finpulse", caption=test_caption)
    print("\n✅ Test carousel saved:")
    for p in paths:
        print(f"  {p}")
