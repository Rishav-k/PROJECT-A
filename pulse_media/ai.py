"""
ai.py — Pulse Media AI Caption Writer
Generates Instagram captions from news articles — 100% FREE.

Backends (tries in order):
  1. Groq  (free — Llama 3.1 70B — 14,400 req/day — best quality)
  2. Gemini (free — Gemini Flash — 1,500 req/day)
  3. Template (zero deps — works with no API key at all)

Setup (pick ONE — both are free):
  Option A: Get free Groq key at https://console.groq.com  (recommended)
  Option B: Get free Gemini key at https://aistudio.google.com/apikey

Add to .env:
  GROQ_API_KEY=gsk_xxxxxxxxxxxx
  OR
  GEMINI_API_KEY=AIzaxxxxxxxxxxxxxxx

Usage:
  python3 ai.py                     # top article from DB, auto-detect backend
  python3 ai.py --page techpulse    # specific page
  python3 ai.py --preview           # show output, don't save to DB
  python3 ai.py --backend template  # force template mode (no API key needed)
"""

from __future__ import annotations

import os, sys, re, json, random, warnings
warnings.filterwarnings("ignore", category=Warning, module="urllib3")


# ─────────────────────────────────────────────
# LOAD .env
# ─────────────────────────────────────────────

import env_loader  # noqa: F401 — loads .env on import


# ─────────────────────────────────────────────
# PAGE PERSONAS
# ─────────────────────────────────────────────

PERSONAS = {
    "finpulse": {
        "name":     "FinPulse",
        "handle":   "@finpulse.daily",
        "role":     "senior financial analyst and market strategist",
        "audience": "retail investors, traders, and finance professionals",
        "tone":     "sharp, data-driven, confident — like a Bloomberg analyst",
        "topics":   "stocks, crypto, Fed policy, earnings, global markets",
    },
    "techpulse": {
        "name":     "TechPulse",
        "handle":   "@techpulse.daily",
        "role":     "senior tech journalist and startup analyst",
        "audience": "developers, founders, tech enthusiasts",
        "tone":     "insightful, forward-thinking — like a TechCrunch editor",
        "topics":   "AI, startups, Big Tech, product launches, cybersecurity",
    },
    "corppulse": {
        "name":     "CorpPulse",
        "handle":   "@corppulse.daily",
        "role":     "corporate strategy analyst and business journalist",
        "audience": "business executives, MBA students, professionals",
        "tone":     "authoritative and analytical — like HBR",
        "topics":   "M&A, CEO moves, corporate strategy, earnings, layoffs",
    },
    "worldpulse": {
        "name":     "WorldPulse",
        "handle":   "@worldpulse.daily",
        "role":     "international affairs analyst",
        "audience": "globally-minded citizens, policy watchers",
        "tone":     "clear, balanced, authoritative — like BBC World",
        "topics":   "geopolitics, elections, conflicts, diplomacy",
    },
}

BASE_HASHTAGS = {
    "finpulse":  "#StockMarket #Investing #Finance #WallStreet #Trading #FinancialNews #Stocks #MarketUpdate #Investment #MoneyMoves",
    "techpulse": "#Tech #AI #Startup #Innovation #Technology #TechNews #ArtificialIntelligence #SiliconValley #Founder #FutureTech",
    "corppulse": "#Business #Corporate #CEO #Strategy #Entrepreneurship #BusinessNews #Leadership #MBA #Economy #CorpPulse",
    "worldpulse": "#WorldNews #Geopolitics #GlobalNews #International #Politics #Breaking #NewsUpdate #WorldAffairs #Diplomacy #GlobalPolitics",
}


# ─────────────────────────────────────────────
# THE PROMPT (same prompt used by all backends)
# ─────────────────────────────────────────────

def build_prompt(article: dict, page: str) -> str:
    persona   = PERSONAS.get(page, PERSONAS["finpulse"])
    base_tags = BASE_HASHTAGS.get(page, "")

    return f"""You are the AI writer for {persona['name']} ({persona['handle']}), a premium Instagram news page.
Your role: {persona['role']}
Your audience: {persona['audience']}
Your tone: {persona['tone']}

NEWS ARTICLE:
Title: {article['title']}
Source: {article.get('source_name', '')}
Summary: {article.get('summary', '')}

Write a high-engagement Instagram post. Use this EXACT structure:

HOOK: [One powerful opening line, 1-2 emojis, max 12 words. Must stop the scroll.]

ANALYSIS:
[Paragraph 1 — What happened and why it matters. 2-3 sentences.]
[Paragraph 2 — Deeper context or background. 2-3 sentences.]
[Paragraph 3 — What happens next / what to watch. 2-3 sentences.]

PROS:
• [Specific positive implication]
• [Specific positive implication]
• [Specific positive implication]

CONS:
• [Specific risk or downside]
• [Specific risk or downside]
• [Specific risk or downside]

WHO BENEFITS:
• [Specific group, sector, or person that gains from this]
• [Specific group, sector, or person that gains from this]
• [Specific group, sector, or person that gains from this]

WHO LOSES:
• [Specific group, sector, or person that loses or faces risk]
• [Specific group, sector, or person that loses or faces risk]
• [Specific group, sector, or person that loses or faces risk]

CTA: [One engaging question to drive comments. Start with: What do you think / Are you / Will you / Drop a]

HASHTAGS: [15 specific hashtags for this story. Do NOT repeat these base tags: {base_tags}]

Rules: Use emojis naturally. Keep total under 2,200 chars. Write as the brand voice, not as "I"."""


# ─────────────────────────────────────────────
# BACKEND 1: GROQ (free — recommended)
# ─────────────────────────────────────────────

def generate_groq(prompt: str) -> tuple[str, int, int]:
    """Call Groq API with Llama 3.1 70B. Returns (text, tokens_in, tokens_out)."""
    import urllib.request
    api_key = os.environ.get("GROQ_API_KEY", "")
    if not api_key:
        raise ValueError("No GROQ_API_KEY in .env")

    # Try models in order — newer ones first, fall back to older stable ones
    GROQ_MODELS = [
        "llama-3.3-70b-versatile",
        "llama3-70b-8192",
        "llama-3.1-70b-versatile",
        "llama-3.1-8b-instant",
    ]
    last_err = None
    for model in GROQ_MODELS:
        try:
            payload = json.dumps({
                "model":       model,
                "messages":    [{"role": "user", "content": prompt}],
                "max_tokens":  1024,
                "temperature": 0.7,
            }).encode()
            req2 = urllib.request.Request(
                "https://api.groq.com/openai/v1/chat/completions",
                data=payload,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type":  "application/json",
                }
            )
            with urllib.request.urlopen(req2, timeout=30) as resp:
                data = json.loads(resp.read())
            text       = data["choices"][0]["message"]["content"]
            tokens_in  = data["usage"]["prompt_tokens"]
            tokens_out = data["usage"]["completion_tokens"]
            print(f"    ✓ Model: {model}")
            return text, tokens_in, tokens_out
        except Exception as e:
            last_err = e
            err_str = str(e)
            # If model not found/deactivated, try next
            if "model_not_active" in err_str or "model_deactivated" in err_str or "does not exist" in err_str or "404" in err_str:
                print(f"    ⚠ Model {model} unavailable, trying next…")
                continue
            # Other errors (auth, rate limit, network) — raise immediately
            raise
    raise last_err or RuntimeError("All Groq models failed")


# ─────────────────────────────────────────────
# BACKEND 2: GOOGLE GEMINI (free)
# ─────────────────────────────────────────────

def generate_gemini(prompt: str) -> tuple[str, int, int]:
    """Call Gemini Flash API. Returns (text, tokens_in, tokens_out)."""
    import urllib.request
    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        raise ValueError("No GEMINI_API_KEY in .env")

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
    payload = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"maxOutputTokens": 1024, "temperature": 0.7},
    }).encode()

    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read())

    text       = data["candidates"][0]["content"]["parts"][0]["text"]
    tokens_in  = data.get("usageMetadata", {}).get("promptTokenCount", 0)
    tokens_out = data.get("usageMetadata", {}).get("candidatesTokenCount", 0)
    return text, tokens_in, tokens_out


# ─────────────────────────────────────────────
# BACKEND 3: TEMPLATE (zero deps, always works)
# ─────────────────────────────────────────────

HOOKS = {
    "finpulse":  ["🚨 BREAKING:", "📈 MARKET ALERT:", "💰 BIG MOVE:", "⚡ JUST IN:", "🔥 WATCH THIS:"],
    "techpulse": ["🤖 AI UPDATE:", "🚀 BREAKING:", "⚡ JUST DROPPED:", "🔥 BIG NEWS:", "💻 TECH ALERT:"],
    "corppulse": ["🏢 CORPORATE MOVE:", "📋 BUSINESS ALERT:", "💼 BREAKING:", "🎯 MAJOR DEAL:", "🔑 CEO WATCH:"],
    "worldpulse":["🌍 BREAKING:", "⚡ WORLD NEWS:", "🔥 DEVELOPING:", "🌐 GLOBAL ALERT:", "📰 JUST IN:"],
}

def generate_template(article: dict, page: str) -> tuple[str, int, int]:
    """Generate a decent caption using templates — zero AI, zero cost."""
    persona   = PERSONAS[page]
    base_tags = BASE_HASHTAGS[page]
    title     = article["title"]
    summary   = article.get("summary", "This is a major development worth tracking closely.")
    source    = article.get("source_name", "Major news source")
    hook_prefix = random.choice(HOOKS.get(page, HOOKS["finpulse"]))

    caption = f"""{hook_prefix} {title} 📊

{summary[:300]}{'...' if len(summary) > 300 else ''}

What this means for you:
✅ Stay informed and ahead of the market
✅ This story could impact your portfolio / strategy
✅ Key players are watching this closely

What to watch:
❌ Uncertainty remains — don't react emotionally
❌ More details expected in coming hours
❌ Multiple outcomes still possible

Source: {source}

💬 What's your take on this? Drop your thoughts below 👇

.
.
.
{base_tags}"""

    return caption, 0, 0


# ─────────────────────────────────────────────
# RESPONSE PARSER
# ─────────────────────────────────────────────

def _parse_response(text: str, base_hashtags: str) -> dict:
    # Use \n + full label so "CONS" doesn't match inside "Consumer"
    def extract(label, stops):
        stop_pat = '|'.join(rf'\n{s}' for s in stops) if stops else ''
        pattern  = rf'(?:^|\n){label}:?\s*\n?(.*?)(?={stop_pat}|\Z)' if stop_pat \
                   else rf'(?:^|\n){label}:?\s*\n?(.*)'
        m = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
        return m.group(1).strip() if m else ""

    hook          = extract("HOOK",         ["ANALYSIS", "PROS", "CONS", "WHO BENEFITS", "WHO LOSES", "CTA", "HASHTAGS"])
    analysis      = extract("ANALYSIS",     ["PROS", "CONS", "WHO BENEFITS", "WHO LOSES", "CTA", "HASHTAGS"])
    pros_raw      = extract("PROS",         ["CONS", "WHO BENEFITS", "WHO LOSES", "CTA", "HASHTAGS"])
    cons_raw      = extract("CONS",         ["WHO BENEFITS", "WHO LOSES", "CTA", "HASHTAGS"])
    benefits_raw  = extract("WHO BENEFITS", ["WHO LOSES", "CTA", "HASHTAGS"])
    losers_raw    = extract("WHO LOSES",    ["CTA", "HASHTAGS"])
    cta           = extract("CTA",          ["HASHTAGS"])
    tags_raw      = extract("HASHTAGS",     [])

    def bullets(s, max_items=3):
        lines = [l.strip().lstrip("•-*1234567890.).").strip() for l in s.splitlines() if l.strip()]
        return [l for l in lines if len(l) > 5][:max_items]

    pros         = bullets(pros_raw)
    cons         = bullets(cons_raw)
    who_benefits = bullets(benefits_raw)
    who_loses    = bullets(losers_raw)

    story_tags   = " ".join(re.findall(r"#\w+", tags_raw))
    all_hashtags = f"{story_tags} {base_hashtags}".strip()

    pros_str     = "\n".join(f"✅ {p}" for p in pros) if pros else ""
    cons_str     = "\n".join(f"❌ {c}" for c in cons) if cons else ""

    parts = []
    if hook:     parts.append(hook)
    if analysis: parts.append("\n" + analysis)
    if pros_str: parts.append("\n📊 IMPLICATIONS:\n" + pros_str)
    if cons_str: parts.append(cons_str)
    if cta:      parts.append("\n💬 " + cta)
    parts.append("\n.\n.\n.\n" + all_hashtags)

    return {
        "caption":      "\n".join(parts),
        "hashtags":     all_hashtags,
        "hook":         hook or text.split("\n")[0],
        "analysis":     analysis,
        "pros":         pros,
        "cons":         cons,
        "who_benefits": who_benefits,
        "who_loses":    who_loses,
        "cta":          cta,
    }


# ─────────────────────────────────────────────
# MAIN GENERATOR — auto-detects best backend
# ─────────────────────────────────────────────

def generate_caption(article: dict, page: str = "finpulse", backend: str = "auto") -> dict:
    """
    Generate an Instagram caption. Auto-picks the best available backend.
    backend: "auto" | "groq" | "gemini" | "template"
    """
    base_tags = BASE_HASHTAGS.get(page, "")
    prompt    = build_prompt(article, page)

    backends_to_try = []
    if backend == "auto":
        if os.environ.get("GROQ_API_KEY"):
            backends_to_try.append("groq")
        if os.environ.get("GEMINI_API_KEY"):
            backends_to_try.append("gemini")
        backends_to_try.append("template")
    else:
        backends_to_try = [backend]

    for b in backends_to_try:
        try:
            print(f"  🤖 Using backend: {b.upper()}")
            if b == "groq":
                raw, tin, tout = generate_groq(prompt)
                cost = 0.0  # Groq is free
            elif b == "gemini":
                raw, tin, tout = generate_gemini(prompt)
                cost = 0.0  # Gemini Flash free tier
            else:
                raw, tin, tout = generate_template(article, page)
                result = _parse_response(raw, base_tags) if b != "template" else {
                    "caption": raw, "hashtags": base_tags,
                    "hook": raw.split("\n")[0], "pros": [], "cons": [], "cta": ""
                }
                result.update({"tokens_in": 0, "tokens_out": 0, "cost_usd": 0.0,
                                "backend": b, "raw": raw})
                return result

            result = _parse_response(raw, base_tags)
            result.update({"tokens_in": tin, "tokens_out": tout,
                           "cost_usd": 0.0, "backend": b, "raw": raw})
            return result

        except Exception as e:
            print(f"  ⚠️  {b} failed: {e}")
            if b == backends_to_try[-1]:
                print("  📋 Falling back to template mode...")
                raw, tin, tout = generate_template(article, page)
                result = {
                    "caption": raw, "hashtags": base_tags,
                    "hook": raw.split("\n")[0], "pros": [], "cons": [], "cta": "",
                    "tokens_in": 0, "tokens_out": 0, "cost_usd": 0.0,
                    "backend": "template", "raw": raw
                }
                return result

    return {}


# ─────────────────────────────────────────────
# SAVE TO DB
# ─────────────────────────────────────────────

def save_to_db(article: dict, result: dict, page: str) -> int:
    from database.models import save_post, mark_article_posted
    post_id = save_post({
        "article_id": article["id"],
        "page":       page,
        "caption":    result["caption"],
        "hashtags":   result["hashtags"],
    })
    mark_article_posted(article["id"])
    return post_id


# ─────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────

def main():
    page    = "finpulse"
    preview = False
    backend = "auto"

    for arg in sys.argv[1:]:
        if arg == "--preview":   preview = True
        elif arg.startswith("--page="):    page    = arg.split("=")[1]
        elif arg.startswith("--backend="): backend = arg.split("=")[1]
        elif arg in ("finpulse","techpulse","corppulse","worldpulse"): page = arg

    from database.models import get_top_articles
    articles = get_top_articles(page, limit=1)

    if not articles:
        print(f"❌ No articles in DB for {page}")
        print(f"   Run: python3 pipeline/orchestrator.py {page}")
        return

    article = articles[0]

    print(f"\n{'='*60}")
    print(f"🤖 AI CAPTION WRITER — {page.upper()}")
    print(f"{'='*60}")
    print(f"📰 {article['title'][:70]}")
    print(f"   Source: {article['source_name']}  |  Score: {article['score']}pts\n")

    result = generate_caption(article, page, backend)
    if not result:
        return

    print(f"\n{'='*60}")
    print("📸 GENERATED INSTAGRAM POST")
    print(f"{'='*60}\n")
    print(result["caption"])
    print(f"\n{'─'*60}")
    print(f"🔧 Backend: {result.get('backend','?').upper()}  |  Cost: ${result['cost_usd']:.4f}  |  Length: {len(result['caption'])} chars")

    if not preview:
        post_id = save_to_db(article, result, page)
        print(f"✅ Saved → Post ID #{post_id}")
        print(f"   Next: python3 image.py to generate the post image")
    else:
        print(f"\n👁  Preview mode — not saved (remove --preview to save)")


if __name__ == "__main__":
    main()
