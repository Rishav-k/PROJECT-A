"""
design_assets.py — FinPulse Premium Visual Assets & Background Generator
Generates high-end finance backgrounds (BSE/NSE/Wall Street silhouettes, trading grids)
and dynamic Bull 🐂 / Bear 🐻 vector emblems.
"""

import math
from PIL import Image, ImageDraw, ImageFont, ImageFilter

SIZE = 1080

def create_gradient_bg(color_top: tuple, color_bottom: tuple) -> Image.Image:
    """Creates a smooth vertical gradient background."""
    base = Image.new("RGB", (SIZE, SIZE), color_top)
    top_img = Image.new("RGB", (SIZE, SIZE), color_top)
    bot_img = Image.new("RGB", (SIZE, SIZE), color_bottom)
    
    # Create vertical alpha mask
    mask = Image.new("L", (SIZE, SIZE))
    for y in range(SIZE):
        alpha = int((y / SIZE) * 255)
        mask.paste(alpha, (0, y, SIZE, y + 1))
        
    return Image.composite(bot_img, top_img, mask)


def add_finance_architectural_silhouettes(im: Image.Image, accent_color: tuple, opacity: float = 0.15):
    """
    Renders stylized financial exchange architectural silhouettes
    (BSE Phiroze Towers, classical Wall St pillars, and geometric stock grid).
    """
    overlay = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    col = (accent_color[0], accent_color[1], accent_color[2], int(255 * opacity))
    col_light = (255, 255, 255, int(255 * (opacity * 0.5)))

    # 1. Subtle Candlestick Watermarks across background
    candles = [
        (120, 650, 720, 600, 780),
        (220, 580, 680, 520, 740),
        (340, 480, 600, 420, 660),
        (460, 520, 640, 490, 680),
        (580, 400, 530, 360, 580),
        (700, 350, 480, 310, 520),
        (820, 280, 420, 240, 460),
        (940, 220, 350, 180, 400),
    ]
    for cx, top_body, bot_body, high, low in candles:
        # Wick
        d.line([(cx, high), (cx, low)], fill=col_light, width=3)
        # Body
        d.rounded_rectangle([(cx - 24, top_body), (cx + 24, bot_body)], radius=6, fill=col)

    # 2. Bottom Architectural Skyline Silhouette (BSE / Wall St Buildings)
    # Background building blocks
    bldgs = [
        (40, 820, 180, 1080),
        (160, 740, 320, 1080),
        (300, 790, 440, 1080),
        (420, 680, 620, 1080),  # Tall Tower (Phiroze Jeejeebhoy Towers)
        (600, 760, 740, 1080),
        (720, 710, 880, 1080),
        (860, 790, 1040, 1080),
    ]
    for x0, y0, x1, y1 in bldgs:
        d.rectangle([(x0, y0), (x1, y1)], fill=(0, 0, 0, int(255 * (opacity * 0.85))))
        # Windows grid
        for wx in range(x0 + 15, x1 - 15, 20):
            for wy in range(y0 + 20, y1 - 40, 28):
                d.rectangle([(wx, wy), (wx + 8, wy + 12)], fill=col_light)

    # 3. Fine technical grid overlay
    for gy in range(100, SIZE, 90):
        d.line([(0, gy), (SIZE, gy)], fill=(255, 255, 255, int(255 * 0.04)), width=1)
    for gx in range(90, SIZE, 90):
        d.line([(gx, 0), (gx, SIZE)], fill=(255, 255, 255, int(255 * 0.04)), width=1)

    im.paste(Image.alpha_composite(im.convert("RGBA"), overlay).convert("RGB"))


def draw_bull_emblem(im: Image.Image, cx: int, cy: int, size: int = 140, glow_color: tuple = (16, 185, 129)):
    """Draws a powerful charging Bull badge with glowing energy."""
    overlay = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)

    r = size // 2
    # Outer Glow Ring
    d.ellipse([(cx - r - 10, cy - r - 10), (cx + r + 10, cy + r + 10)], fill=(glow_color[0], glow_color[1], glow_color[2], 60))
    d.ellipse([(cx - r, cy - r), (cx + r, cy + r)], fill=(16, 24, 39, 230), outline=(glow_color[0], glow_color[1], glow_color[2], 240), width=4)

    # Geometric Bull Horns & Head
    # Horns
    d.arc([(cx - 45, cy - 40), (cx - 15, cy - 10)], start=160, end=340, fill=(glow_color[0], glow_color[1], glow_color[2], 255), width=6)
    d.arc([(cx + 15, cy - 40), (cx + 45, cy - 10)], start=200, end=380, fill=(glow_color[0], glow_color[1], glow_color[2], 255), width=6)
    # Head & Snout Shield
    d.polygon([(cx - 30, cy - 15), (cx + 30, cy - 15), (cx + 20, cy + 30), (cx, cy + 42), (cx - 20, cy + 30)], fill=(glow_color[0], glow_color[1], glow_color[2], 255))
    # Eyes
    d.ellipse([(cx - 15, cy), (cx - 7, cy + 6)], fill=(255, 255, 255, 255))
    d.ellipse([(cx + 7, cy), (cx + 15, cy + 6)], fill=(255, 255, 255, 255))
    # Snout ring
    d.arc([(cx - 10, cy + 22), (cx + 10, cy + 38)], start=0, end=180, fill=(255, 255, 255, 220), width=3)

    im.paste(Image.alpha_composite(im.convert("RGBA"), overlay).convert("RGB"))


def draw_bear_emblem(im: Image.Image, cx: int, cy: int, size: int = 140, glow_color: tuple = (223, 48, 28)):
    """Draws a fierce roaring Bear badge."""
    overlay = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)

    r = size // 2
    # Outer Glow Ring
    d.ellipse([(cx - r - 10, cy - r - 10), (cx + r + 10, cy + r + 10)], fill=(glow_color[0], glow_color[1], glow_color[2], 60))
    d.ellipse([(cx - r, cy - r), (cx + r, cy + r)], fill=(28, 15, 15, 230), outline=(glow_color[0], glow_color[1], glow_color[2], 240), width=4)

    # Geometric Bear Ears & Snout
    # Ears
    d.ellipse([(cx - 38, cy - 35), (cx - 18, cy - 15)], fill=(glow_color[0], glow_color[1], glow_color[2], 255))
    d.ellipse([(cx + 18, cy - 35), (cx + 38, cy - 15)], fill=(glow_color[0], glow_color[1], glow_color[2], 255))
    # Head
    d.ellipse([(cx - 32, cy - 25), (cx + 32, cy + 32)], fill=(glow_color[0], glow_color[1], glow_color[2], 255))
    # Snout
    d.ellipse([(cx - 16, cy + 2), (cx + 16, cy + 26)], fill=(255, 255, 255, 240))
    d.polygon([(cx - 8, cy + 6), (cx + 8, cy + 6), (cx, cy + 14)], fill=(28, 15, 15, 255))
    # Fierce Eyes
    d.polygon([(cx - 20, cy - 8), (cx - 8, cy - 3), (cx - 16, cy + 1)], fill=(255, 255, 255, 255))
    d.polygon([(cx + 20, cy - 8), (cx + 8, cy - 3), (cx + 16, cy + 1)], fill=(255, 255, 255, 255))

    im.paste(Image.alpha_composite(im.convert("RGBA"), overlay).convert("RGB"))
