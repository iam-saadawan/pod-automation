import os
import json
import time
import requests
from io import BytesIO
from urllib.parse import quote
from PIL import Image
from rembg import remove
from dotenv import load_dotenv

load_dotenv()

POLLINATIONS_API_KEY = os.getenv("POLLINATIONS_API_KEY")
OUTPUT_DIR = "designs"


def build_full_prompt(concept):
    """Build a detailed, print-ready prompt from a concept dict."""
    base = concept["image_prompt"]
    slogan = concept.get("slogan", "")
    style = concept.get("style", "")
    placement = concept.get("placement", "front center")
    has_text = concept.get("has_text", bool(slogan))

    text_instruction = (
        f'The shirt slogan text is: "{slogan}". '
        f'Render this text in bold, clearly legible typography that matches the style. '
        f'Make the text a central design element, not an afterthought.'
    ) if has_text and slogan else (
        "This is a pure graphic design — no text, no words, no letters at all."
    )

    placement_instruction = (
        "Design should be vertically tall and centered, filling the chest-to-waist print area."
        if "waist" in placement else
        "Design should be compact and bold, suitable for a chest-width print."
        if "left chest" in placement or "small" in placement else
        "Design should be large, bold, and centered for maximum visual impact."
    )

    return (
        f"{base} "
        f"{text_instruction} "
        f"{placement_instruction} "
        f"Style reference: {style}. "
        f"Technical requirements: pure white background, "
        f"centered composition, high detail level, bold confident outlines, "
        f"vibrant saturated colors, NO watermarks, NO signatures, NO photo realism, "
        f"NO gradients unless they match the style, print-ready vector-style artwork, "
        f"professional t-shirt graphic quality."
    )


def generate_image(concept):
    """Generate image via Pollinations Flux."""
    full_prompt = build_full_prompt(concept)
    encoded = quote(full_prompt)
    url = (
        f"https://gen.pollinations.ai/image/{encoded}"
        f"?model=flux&width=2048&height=2048&nologo=true&key={POLLINATIONS_API_KEY}"
    )

    response = requests.get(url, timeout=90)

    if response.status_code != 200:
        print(f"  ERROR ({response.status_code}): {response.text[:200]}")
        return None

    if len(response.content) < 5000:
        print(f"  ERROR: response too small ({len(response.content)} bytes) — likely an error message")
        return None

    return response.content


def remove_background_and_save(image_bytes, output_path):
    """Strip white background and save as transparent PNG."""
    img = Image.open(BytesIO(image_bytes)).convert("RGBA")
    result = remove(img)
    result.save(output_path, "PNG")


if __name__ == "__main__":
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    with open("niches.json", "r") as f:
        data = json.load(f)

    concepts = data["concepts"]
    niche = data.get("niche", "unknown niche")
    print(f"Generating {len(concepts)} designs for niche: '{niche}'\n")

    results = []

    for i, concept in enumerate(concepts, 1):
        filename = f"design_{i:02d}.png"
        output_path = os.path.join(OUTPUT_DIR, filename)

        print(f"[{i}/{len(concepts)}] {concept['title']}")
        print(f"  Style: {concept.get('style', '')[:65]}...")
        print(f"  Placement: {concept.get('placement', 'front center')}")
        print(f"  Has text: {concept.get('has_text', False)} — '{concept.get('slogan', '')}'")

        image_bytes = generate_image(concept)

        if image_bytes is None:
            print(f"  Skipped.")
            time.sleep(2)
            continue

        try:
            print(f"  Removing background...")
            remove_background_and_save(image_bytes, output_path)
            size_kb = os.path.getsize(output_path) // 1024
            print(f"  Saved -> {output_path} ({size_kb} KB, transparent PNG)")
            results.append({
                "filename": filename,
                "title": concept["title"],
                "slogan": concept.get("slogan", ""),
                "placement": concept.get("placement", "front center"),
            })
        except Exception as e:
            print(f"  ERROR during background removal: {e}")

        time.sleep(2)

    with open(os.path.join(OUTPUT_DIR, "manifest.json"), "w") as f:
        json.dump(results, f, indent=2)

    print(f"\nDone. {len(results)}/{len(concepts)} images saved.")
    print(f"Manifest: {OUTPUT_DIR}/manifest.json")