import os
import json
import random
import time
import requests
from urllib.parse import quote_plus
# pyrefly: ignore [missing-import]
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"

# ── Curated niche pool ──────────────────────────────────────────────────────
# Each niche has been validated against:
#   1. Buyer identity test — someone says "that's SO me"
#   2. Demand signal — 1k+ results with visible sales on Etsy
#   3. Specificity — 2 levels deeper than "funny shirt"
#   4. IP-safe — zero trademark/fandom dependence
#
# Grouped by design direction (cartoonish / anime / automotive / lifestyle)
NICHE_POOL = [
    # Anime / cartoon identity niches
    "sarcastic introvert who hates small talk",
    "anime-obsessed gamer who never goes outside",
    "chaotic cat owner with zero control",
    "chronically online night owl",
    "overly caffeinated creative who runs on coffee and anxiety",
    # Humor identity niches (work well with cartoon art)
    "gym rat who skips leg day and knows it",
    "nurse who survives on dark humor and caffeine",
    "exhausted teacher who needs summer break",
    "dog dad who treats his dog like a child",
    "overthinker with anxiety who laughs about it",
    # Trending mashup niches (cartoon + attitude)
    "plant mom who talks to her plants",
    "true crime obsessed introvert",
    "bookworm who cancels plans to read",
    "burnt out millennial running on fumes",
    "chaotic good friend who gives terrible advice",
    # Automotive / Car enthusiast niches
    "JDM street racing car enthusiast",
    "classic vintage muscle car lover",
    "off-road 4x4 overland adventurer",
    "cyberpunk futuristic car culture fan",
    # Tech & Lifestyle niches
    "retro arcade video gamer",
    "caffeine addict who runs on espresso",
    "mechanical keyboard typing enthusiast",
]

# ── Placements ───────────────────────────────────────────────────────────────
# Front-only, weighted toward large center (best sellers)
PLACEMENTS = [
    "front center — large graphic filling chest area",
    "front center — oversized print from chest to waist",
    "front left chest — small bold logo style",
]

# ── Visual styles (ONLY styles Flux renders clean + survive rembg) ───────────
# Every style here produces: bold outlines, flat fills, hard edges, clean
# silhouettes. Removed: chrome/Y2K, psychedelic gradients, grunge/distressed,
# gothic blackletter (Flux can't do typography).
DESIGN_STYLES = [
    (
        "chibi anime — cute exaggerated proportions, big head small body, "
        "bold black outlines, flat cel-shaded colors, kawaii aesthetic, "
        "expressive oversized eyes, clean vector-style artwork"
    ),
    (
        "bold cartoon sticker art — thick black outlines like a die-cut sticker, "
        "vibrant flat color fills with zero gradients, clean sharp edges, "
        "exaggerated cartoon proportions, pop art energy"
    ),
    (
        "kawaii cute horror — adorable character with creepy twist, pastel colors "
        "mixed with dark elements, bold outlines, flat fills, cute big eyes, "
        "screen-print style clean edges"
    ),
    (
        "retro 90s-2000s cartoon — Saturday morning cartoon style, bold cel-shading, "
        "flat vibrant colors, thick confident outlines, dynamic exaggerated pose, "
        "like Powerpuff Girls or Dexter's Lab aesthetic"
    ),
    (
        "tattoo flash art — traditional American tattoo style, bold black outlines, "
        "limited flat color palette (3-4 colors max), clean isolated design, "
        "screen-print ready, no shading gradients"
    ),
    (
        "anime streetwear — clean anime illustration, Harajuku aesthetic, high contrast, "
        "bold black stroke outlines, flat color fills, minimal background, "
        "single character with attitude"
    ),
    (
        "minimalist bold cartoon — one powerful cartoon character or element, "
        "maximum negative space, thick outlines, 2-3 flat colors only, "
        "clean silhouette, modern streetwear drop energy"
    ),
    (
        "retro anime cel — 80s-90s anime aesthetic, warm flat color fills, "
        "bold confident linework, slight vintage feel but clean edges, "
        "single character portrait or bust, screen-print style"
    ),
    (
        "cartoon car sticker art — exaggerated proportions, thick black outlines, "
        "bold tires and lights, flat color fills, classic JDM or retro muscle car shape, "
        "pop art cartoon energy"
    ),
    (
        "retro automotive line art — clean vintage car silhouette, minimalist line drawing, "
        "bold confident black strokes, 2-3 retro flat color fills, screen-print vector look"
    ),
    (
        "vintage travel badge art — circle or shield-shaped layout, retro camper or "
        "4x4 off-road vehicle in center, thick outlines, flat fills, clean isolated emblem"
    ),
    (
        "pop art object illustration — single retro lifestyle object (e.g. cassette tape, "
        "mechanical keyboard switch, retro game console) in bold pop art style, thick borders, "
        "clean high-contrast flat fills"
    ),
]


def scrape_ebay_trends(niche):
    """Scrape eBay search suggestions as trend research (we sell on Shopify, but eBay
    autosuggest reveals what POD buyers are actually searching for)."""
    try:
        query = quote_plus(f"{niche} shirt")
        url = f"https://autosug.ebay.com/autosug?sId=0&q={query}&fmt=osr"
        response = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        data = response.json()
        suggestions = data.get("res", {}).get("sug", [])
        return suggestions[:8]
    except Exception as e:
        print(f"  eBay trend scrape failed (non-critical): {e}")
        return []


def scrape_etsy_trends(niche):
    """Scrape Etsy search suggestions as trend research (Etsy is the biggest POD
    marketplace — their search data reveals proven demand even though we sell on Shopify)."""
    try:
        query = quote_plus(f"{niche} shirt")
        url = f"https://www.etsy.com/search/suggest?q={query}"
        response = requests.get(url, timeout=10, headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"
        })
        # Etsy returns a JSON array of suggestion strings
        data = response.json()
        if isinstance(data, list):
            return [s for s in data if isinstance(s, str)][:8]
        return []
    except Exception as e:
        print(f"  Etsy trend scrape failed (non-critical): {e}")
        return []


def get_design_concepts(niche, trend_signals):
    """Ask Gemini for 10 design concepts optimized for Flux + rembg pipeline."""

    # Assign random styles and placements — weighted toward large center prints
    assignments = [
        {
            "style": random.choice(DESIGN_STYLES),
            "placement": random.choice(PLACEMENTS),
            # 50/50 split: half graphic-only, half with text slogans
            "has_text": i >= 5,
        }
        for i in range(10)
    ]
    random.shuffle(assignments)

    trend_context = (
        f"Real buyer search trends for this niche: {', '.join(trend_signals)}"
        if trend_signals
        else "No trend data available — use your expert judgment on what's selling right now."
    )

    prompt = f"""You are a senior creative director for Urban Vault, a premium streetwear brand selling cartoon/anime-style graphic tees on Shopify (marketed via TikTok/Reels/Shorts). You specialize in designs that the target buyer sees and instantly says "that's SO me — I need this."

NICHE: {niche}
{trend_context}

Generate exactly 10 t-shirt design concepts. Each has a pre-assigned style, placement, and text mode.

ASSIGNMENTS:
{chr(10).join(f'{i+1}. STYLE: {a["style"]} | PLACEMENT: {a["placement"]} | HAS_TEXT: {a["has_text"]}' for i, a in enumerate(assignments))}

═══ ABSOLUTE RULES ═══

RULE 1 — SIMPLE SINGLE SUBJECT: Every design has ONE clear focal subject (a character, a car, or an object). NOT a complex scene with multiple interacting elements. Think: one high-impact subject with attitude and personality, filling the frame.
  GOOD: "a chibi cat in a hoodie, arms crossed, annoyed expression" or "a cartoon classic retro muscle car, 3/4 front view angle, big rear tires"
  BAD: "a car on a race track in a lightning storm with a crowd of people watching and explosions in the background"
  The simpler and bolder the subject, the better it prints on a shirt.

RULE 2 — REMBG-SAFE ART DIRECTION: The design will be generated on a white background and then the background will be removed with AI. To survive this cleanly, EVERY image_prompt MUST include these exact phrases:
  "isolated on solid pure white background, screen-print style, flat solid color fills, thick bold black outlines, hard edges, no gradients, no glow, no drop shadow, no soft airbrush, no shading, no gray smudges, no smoke, no mist, no particles, generous margin around artwork, nothing touching canvas edges"

RULE 3 — NO TRADEMARKS: Never reference any real brand, logo, company, celebrity, anime character name, specific car manufacturer/model name (e.g., use "retro JDM sports coupe" instead of "Mazda RX7"), or copyrighted property anywhere. Use generic aesthetic descriptions only.

RULE 4 — FOCUS SUBJECT (CHARACTER, CAR, or ICONIC OBJECT): Choose the best subject type for the niche:
  - For personal/humor/introvert niches: use characters (people, animals, creatures) with expressive poses and facial expressions.
  - For automotive/car niches: use clean JDM cars, retro sports cars, or rugged 4x4 trucks as the single subject.
  - For lifestyle/tech niches: use single iconic items (retro cassettes, retro controllers, keyboard keys, moka coffee pots) with bold pop art outlines.

RULE 5 — IDENTITY RESONANCE: Before writing each concept, ask yourself: "Would the target buyer ({niche}) screenshot this and send it to a friend saying 'this is literally me'?" If not, scrap it and think of something better.

═══ TEXT vs GRAPHIC-ONLY ═══

For concepts where has_text is TRUE:
- Write a short, punchy slogan (max 8 words) that the target niche would LOVE
- The slogan goes in the "slogan" field — it will be added to the design programmatically (NOT by the image AI)
- The image_prompt should describe ONLY the graphic/illustration part — NO text in the image
- Think: the graphic is the subject, the text is added as typography below/above it later

For concepts where has_text is FALSE:
- Set slogan to empty string
- The design must be compelling as a pure illustration — strong enough to sell without words

═══ OUTPUT FORMAT ═══

For each concept provide:
1. "title" — Shopify product title (max 10 words, catchy and brandable, include style keywords like Funny/Graphic/Automotive/Retro/Tee)
2. "slogan" — the text slogan if has_text is true, empty string if false
3. "style" — copy the assigned style string exactly
4. "placement" — copy the assigned placement string exactly
5. "has_text" — copy the assigned boolean exactly
6. "image_prompt" — a detailed Flux image AI prompt following this EXACT structure:
   [STYLE] name the exact art style in 2 different ways
   [SUBJECT] ONE main subject (e.g., character, car, or retro object) in a specific pose/angle, clean shape, high-contrast parts, no complex background elements
   [COMPOSITION] "isolated on solid pure white background, centered composition, single cohesive graphic, generous margin around artwork, nothing touching canvas edges"
   [COLORS] exactly 3-4 named flat colors (e.g. "limited flat color palette: jet black, cherry red, cream white")
   [EDGES] "screen-print style, thick bold black outlines, flat solid color fills, hard edges, no gradients, no glow, no drop shadow, no soft airbrush, no shading, no gray smudges"
   [NEGATIVE] "no text, no words, no letters, no numbers, no watermark, no mockup, no t-shirt, no photo realism, no background scenery, no frame, no border"

Respond ONLY with valid JSON — no markdown, no explanation, no code fences:
{{"concepts": [{{"title": "...", "slogan": "...", "style": "...", "placement": "...", "has_text": true, "image_prompt": "..."}}]}}"""

    payload = {"contents": [{"parts": [{"text": prompt}]}]}

    # Retry up to 3 times on server errors (503, 429, etc.)
    for attempt in range(3):
        response = requests.post(GEMINI_URL, json=payload, timeout=60)
        if response.status_code < 500:
            break
        print(f"  Gemini returned {response.status_code}, retrying in 10s... (attempt {attempt+1}/3)")
        time.sleep(10)

    response.raise_for_status()

    raw = response.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()

    parsed = json.loads(raw)
    return parsed["concepts"] if isinstance(parsed, dict) else parsed


if __name__ == "__main__":
    niche = random.choice(NICHE_POOL)
    print(f"Selected niche: '{niche}'\n")

    # Gather trend signals from multiple sources
    print("Scraping trend signals...")
    ebay_trends = scrape_ebay_trends(niche)
    etsy_trends = scrape_etsy_trends(niche)
    all_trends = list(set(ebay_trends + etsy_trends))

    if all_trends:
        print(f"  Found {len(all_trends)} trend signals:")
        for t in all_trends:
            print(f"    • {t}")
    else:
        print("  No trend signals found — Gemini will use expert judgment.")
    print()

    print("Generating 10 design concepts via Gemini...\n")
    concepts = get_design_concepts(niche, all_trends)

    text_count = sum(1 for c in concepts if c.get("has_text"))
    graphic_count = len(concepts) - text_count

    print(f"Generated {len(concepts)} concepts ({graphic_count} graphic-only, {text_count} with text)\n")

    for i, c in enumerate(concepts, 1):
        print(f"{i}. {c.get('title', 'Untitled')}")
        if c.get("slogan"):
            print(f"   Slogan: \"{c['slogan']}\"")
        else:
            print(f"   (graphic only)")
        print(f"   Style: {c.get('style', '')[:70]}...")
        print(f"   Placement: {c.get('placement', 'front center')}")
        print()

    with open("niches.json", "w") as f:
        json.dump({"niche": niche, "concepts": concepts}, f, indent=2)

    print(f"Saved to niches.json")