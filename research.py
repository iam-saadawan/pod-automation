import os
import json
import requests
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
NICHE = "funny gym and fitness humor"  # Change this to whatever niche you want to test

GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"


def get_design_concepts(niche):
    """Ask Gemini for 10 t-shirt design concepts for a given niche, returned as structured JSON."""

    prompt = f"""You are a print-on-demand t-shirt design strategist for an eBay seller.

Niche: {niche}

Generate exactly 10 t-shirt design concepts for this niche. For each one, provide:
1. "title" - a short product title (max 8 words) good for eBay search/SEO
2. "slogan" - the text that would appear on the shirt (can be empty string if it's a pure graphic design)
3. "image_prompt" - a detailed prompt for an AI image generator to create this design. Must specify: flat vector illustration style, bold simple shapes, 2-4 flat colors, white or transparent background, no photorealism, print-ready for apparel.

Respond ONLY with valid JSON in this exact format, no markdown, no explanation:
{{
  "concepts": [
    {{"title": "...", "slogan": "...", "image_prompt": "..."}},
    ...
  ]
}}
"""

    payload = {
        "contents": [
            {"parts": [{"text": prompt}]}
        ]
    }

    response = requests.post(GEMINI_URL, json=payload)
    response.raise_for_status()
    data = response.json()

    raw_text = data["candidates"][0]["content"]["parts"][0]["text"]

    raw_text = raw_text.strip()
    if raw_text.startswith("```"):
        raw_text = raw_text.split("```")[1]
        if raw_text.startswith("json"):
            raw_text = raw_text[4:]
    raw_text = raw_text.strip()

    concepts = json.loads(raw_text)
    return concepts["concepts"]


if __name__ == "__main__":
    print(f"Generating design concepts for niche: '{NICHE}'...\n")
    concepts = get_design_concepts(NICHE)

    print(f"Got {len(concepts)} concepts:\n")
    for i, c in enumerate(concepts, 1):
        print(f"{i}. {c['title']}")
        print(f"   Slogan: {c['slogan']}")
        print(f"   Prompt: {c['image_prompt'][:80]}...")
        print()

    with open("niches.json", "w") as f:
        json.dump({"niche": NICHE, "concepts": concepts}, f, indent=2)

    print("Saved all concepts to niches.json")