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


def generate_image(prompt):
    """Send a prompt to Pollinations' Flux model and return raw image bytes."""

    full_prompt = (
        f"{prompt}, flat vector illustration, bold simple shapes, "
        f"white background, clean print-ready design, no watermark, centered composition"
    )

    encoded_prompt = quote(full_prompt)
    url = (
        f"https://gen.pollinations.ai/image/{encoded_prompt}"
        f"?model=flux&width=1024&height=1024&nologo=true&key={POLLINATIONS_API_KEY}"
    )

    response = requests.get(url, timeout=60)

    if response.status_code != 200:
        print(f"  ERROR ({response.status_code}): {response.text[:200]}")
        return None

    if len(response.content) < 5000:
        print(f"  ERROR: response too small ({len(response.content)} bytes), likely not an image")
        print(f"  Response: {response.text[:200]}")
        return None

    return response.content


def remove_background_and_save(image_bytes, output_path):
    """Take raw image bytes (with white/solid background), strip the background, save as PNG."""
    input_image = Image.open(BytesIO(image_bytes)).convert("RGBA")
    output_image = remove(input_image)
    output_image.save(output_path, "PNG")


if __name__ == "__main__":
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    with open("niches.json", "r") as f:
        data = json.load(f)

    concepts = data["concepts"]
    print(f"Generating images for {len(concepts)} concepts using Pollinations (Flux)...\n")

    results = []

    for i, concept in enumerate(concepts, 1):
        filename = f"design_{i:02d}.png"
        output_path = os.path.join(OUTPUT_DIR, filename)

        print(f"[{i}/{len(concepts)}] {concept['title']}")

        image_bytes = generate_image(concept["image_prompt"])

        if image_bytes is None:
            print(f"  Skipped (generation failed)")
            time.sleep(2)
            continue

        try:
            print(f"  Removing background...")
            remove_background_and_save(image_bytes, output_path)
            size_kb = os.path.getsize(output_path) // 1024
            print(f"  Saved -> {output_path} ({size_kb} KB, transparent)")
            results.append({
                "filename": filename,
                "title": concept["title"],
                "slogan": concept["slogan"]
            })
        except Exception as e:
            print(f"  ERROR removing background: {e}")

        time.sleep(2)

    with open(os.path.join(OUTPUT_DIR, "manifest.json"), "w") as f:
        json.dump(results, f, indent=2)

    print(f"\nDone. {len(results)}/{len(concepts)} images generated successfully.")
    print(f"Manifest saved to {OUTPUT_DIR}/manifest.json")