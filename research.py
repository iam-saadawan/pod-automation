import os
import json
import random
import time
import requests
from urllib.parse import quote_plus
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"

# Niche pool — one gets picked randomly each run
NICHE_POOL = [
    "funny gym and fitness humor",
    "nurse and healthcare worker humor",
    "dog lover and pet owner humor",
    "teacher and school humor",
    "coffee addict humor",
    "gamer and gaming culture",
    "cat lover humor",
    "construction worker and tradesman humor",
    "anxiety and mental health humor",
    "truck driver and road life",
    "hiking and outdoor adventure",
    "sarcastic introvert humor",
    "dad jokes and father humor",
    "retired life humor",
    "anime and manga streetwear",
]

# Placement options — front-only, varied positioning
PLACEMENTS = [
    "front center — large graphic filling chest area",
    "front center — oversized print from chest to waist",
    "front left chest — small bold logo style",
    "front center — wide horizontal banner across chest",
]

# Visual style directions
DESIGN_STYLES = [
    "bold streetwear graphic — stacked block typography, heavy black outlines, urban hype aesthetic, like a 90s skate brand",
    "expressive cartoon character — anime style character with attitude, dynamic action pose, bold cel-shading, vibrant flat colors, like 2000s Saturday morning cartoons",
    "retro vintage distressed — worn-in 80s biker/band tee aesthetic, grunge texture overlays, faded serif typography, cracked-print look",
    "Y2K chrome and metal — shiny metallic text, chrome bubble letters, holographic aesthetic, like early 2000s hip hop merch",
    "Japanese streetwear — clean minimal kanji + bold graphic, Harajuku aesthetic, high contrast, tattoo-flash inspired",
    "gothic blackletter — ornate medieval typography, dark dramatic aesthetic, like a metal band tee crossed with luxury fashion",
    "psychedelic retro — 70s groovy swirling shapes, sunset gradient colors, bold hand-lettering, like a vintage rock concert poster",
    "minimalist bold — one powerful graphic element with dynamic pose or motion, maximum negative space, like a modern streetwear drop",
]


def scrape_ebay_trends(niche):
    """Scrape eBay search suggestions for real buyer demand signals."""
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


def get_design_concepts(niche, ebay_trends):
    """Ask Gemini for 10 mega-prompted design concepts."""

    # Assign random styles and placements to each of the 10 concepts
    assignments = [
        {
            "style": random.choice(DESIGN_STYLES),
            "placement": random.choice(PLACEMENTS),
        }
        for _ in range(10)
    ]

    trend_context = (
        f"Real eBay buyer search trends for this niche: {', '.join(ebay_trends)}"
        if ebay_trends
        else "No trend data available — use your best judgment on what sells."
    )

    prompt = f"""You are a senior creative director and world class designer for Urban Vault, a premium streetwear and graphic tee brand selling on eBay and Etsy.

NICHE: {niche}
{trend_context}

Your job: Generate exactly 10 BOLD, VISUALLY STRIKING t-shirt design concepts that people actually want to buy.
NOT basic. NOT generic clipart. Think: would someone pay $35 for this and wear it proudly?

Each concept has a pre-assigned visual style and placement. You MUST follow them exactly.

STYLE + PLACEMENT ASSIGNMENTS:
{chr(10).join(f"{i+1}. STYLE: {a['style']} | PLACEMENT: {a['placement']}" for i, a in enumerate(assignments))}

CRITICAL RULE — NEVER reference or reproduce any real brand, logo, wordmark, or company name (e.g. Supreme, Harley Davidson, BAPE, Nike, any real company) anywhere in title, style, or image_prompt. Use only generic aesthetic descriptions. This is a legal requirement — trademarked content cannot be sold.

CRITICAL RULE — NEVER design a single static object floating alone (e.g. just "a hammer", just "a paw print", just "a coffee cup"). That reads as boring clipart and nobody buys it. Every concept MUST have a SCENE: an action, a pose, a collision, an environment, or a character with attitude built around the subject.
   BAD (reject this): "a hammer" / "a paw print" / "a coffee cup icon"
   GOOD: "a battle-worn hammer mid-swing smashing through a cracked concrete wall, sparks and debris flying, dramatic low angle" / "a snarling wolf mid-howl standing on a cliff edge in a lightning storm" / "a steaming coffee cup with a skeleton hand gripping it, cracked mug, dripping coffee like blood"
   Think of it like a tattoo flash sheet or a metal band tee — always motion, drama, or character, never a flat icon.

For each concept provide:
1. "title" — eBay product title (max 10 words, SEO-optimized, include keywords like Funny/Graphic/Streetwear/Tee)
2. Pure graphic design ONLY — absolutely NO text, NO words, NO letters, NO numbers anywhere in the image
3. The design must work as a standalone illustration without any typography
4. "style" — copy the assigned style exactly
5. "placement" — copy the assigned placement exactly
6. "has_text" — always false
7. "image_prompt" — a HIGHLY DETAILED prompt for Flux image AI. Must include ALL of:
   - Exact visual style (name the aesthetic reference e.g. "Ben10 cartoon style", "Supreme box logo style")
   - A concrete SCENE per the CRITICAL RULE above — subject + action/pose + environment or interacting element, not a bare object
   - If has_text is true: exact slogan text, typography style, where text sits relative to graphic
   - Color palette (name 3-5 specific colors e.g. "fire red, jet black, cream white")
   - Energy/mood (aggressive, nostalgic, funny, cool, rebellious)
   - Technical: white background, centered composition, NO watermarks, NO photo realism, print-ready vector artwork, bold outlines

Respond ONLY with valid JSON — no markdown, no explanation, no code fences:
{{"concepts": [{{"title": "...", "slogan": "...", "style": "...", "placement": "...", "has_text": true, "image_prompt": "..."}}]}}"""

    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    
    # Retry up to 3 times on server errors (503, 429, etc.)
    for attempt in range(3):
        response = requests.post(GEMINI_URL, json=payload, timeout=30)
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

    print("Scraping eBay for trend signals...")
    ebay_trends = scrape_ebay_trends(niche)
    if ebay_trends:
        print(f"Found {len(ebay_trends)} eBay trend signals: {', '.join(ebay_trends)}")
    print()

    print("Generating 10 design concepts via Gemini...\n")
    concepts = get_design_concepts(niche, ebay_trends)

    for i, c in enumerate(concepts, 1):
        print(f"{i}. {c.get('title', 'Untitled')}")
        print(f"   Slogan: {c.get('slogan') or '(graphic only)'}")
        print(f"   Style: {c.get('style', '')[:70]}...")
        print(f"   Placement: {c.get('placement', 'front center')}")
        print()

    with open("niches.json", "w") as f:
        json.dump({"niche": niche, "concepts": concepts}, f, indent=2)

    print(f"Saved to niches.json")