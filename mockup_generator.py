import os
import json
import time
import requests
from urllib.parse import quote
from dotenv import load_dotenv

load_dotenv()

POLLINATIONS_API_KEY = os.getenv("POLLINATIONS_API_KEY")
DESIGNS_DIR = "designs"
MOCKUPS_DIR = os.path.join(DESIGNS_DIR, "mockups")
MANIFEST_PATH = os.path.join(DESIGNS_DIR, "manifest.json")

# 4 Premium 3D AI Mockup styles (from KAGE Brand Spec & Skill Bible)
MOCKUP_PROMPTS = {
    "floating_3d": (
        "Ultra-realistic high-end streetwear commercial product photography, "
        "3D floating render of a premium {apparel_type} hovering in mid-air with dynamic rim lighting, "
        "dramatic cast shadow on a dark slate gradient studio background, sharp spotlight, "
        "featuring a high-contrast front graphic print of {subject_summary}, "
        "clean luxury fashion lookbook render, 8k resolution, cinematic lighting, no model, no human, product only"
    ),
    "flatlay": (
        "Minimalist dark studio flat-lay apparel photography, "
        "a neatly folded premium {apparel_type} laid on a matte black textured slate surface, "
        "overhead top-down perspective, subtle directional spotlight casting soft shadow halo, "
        "crisp visible front chest print of {subject_summary}, streetwear editorial lookbook, 8k, no human"
    ),
    "mannequin": (
        "Ghost mannequin invisible form product photography of a premium {apparel_type}, "
        "floating 3D tailored fit showing fabric weight and drape, dark moody studio backdrop, "
        "subtle cyan and crimson rim lighting accentuating the front artwork of {subject_summary}, "
        "high fashion catalog photography, crisp sharp detail, no human"
    ),
    "fabric_detail": (
        "Cinematic extreme macro close-up detail shot of heavy cotton streetwear garment weave, "
        "shallow depth of field, focused squarely on the textured screen-print ink of {subject_summary}, "
        "luxurious fabric micro-texture, dramatic side raking light, dark aesthetic, 8k"
    )
}


def build_mockup_prompt(design, style_key="floating_3d", apparel_type="heavy streetwear t-shirt"):
    """Format the mockup prompt using the design's character, title, and palette."""
    character = design.get("character", "KAGE entity")
    title = design.get("title", "")
    bg_color = design.get("bg_color", "#000000")
    
    color_desc = "black" if bg_color == "#000000" else "deep navy" if bg_color == "#1B2838" else "dark charcoal"
    apparel_str = f"{color_desc} {apparel_type}"
    subject_summary = f"{character} ({title})"

    template = MOCKUP_PROMPTS.get(style_key, MOCKUP_PROMPTS["floating_3d"])
    return template.format(apparel_type=apparel_str, subject_summary=subject_summary)


def generate_mockup_image(prompt, width=1024, height=1024):
    """Generate mockup via Pollinations Flux."""
    encoded = quote(prompt)
    url = f"https://gen.pollinations.ai/image/{encoded}?model=flux&width={width}&height={height}&nologo=true"
    if POLLINATIONS_API_KEY:
        url += f"&key={POLLINATIONS_API_KEY}"

    for attempt in range(3):
        try:
            r = requests.get(url, timeout=90)
            if r.status_code == 200 and len(r.content) > 5000:
                return r.content
            print(f"  Attempt {attempt+1}: Status {r.status_code}, content length {len(r.content)}")
        except Exception as e:
            print(f"  Attempt {attempt+1} failed: {e}")
        time.sleep(3)

    return None


def generate_mockups_for_design(design, styles=None):
    """Generate selected mockup styles for a design and return dictionary of local paths."""
    if styles is None:
        styles = ["floating_3d"]  # Primary hero style

    os.makedirs(MOCKUPS_DIR, exist_ok=True)
    cid = design.get("id", "design")
    mockup_paths = {}

    for style in styles:
        out_filename = f"{cid}_{style}.jpg"
        out_path = os.path.join(MOCKUPS_DIR, out_filename)

        if os.path.exists(out_path) and os.path.getsize(out_path) > 5000:
            print(f"  Mockup [{style}] already exists -> {out_path}")
            mockup_paths[style] = out_path
            continue

        print(f"  Generating [{style}] mockup...")
        prompt = build_mockup_prompt(design, style_key=style)
        img_bytes = generate_mockup_image(prompt)

        if img_bytes:
            with open(out_path, "wb") as f:
                f.write(img_bytes)
            size_kb = len(img_bytes) // 1024
            print(f"  ✓ Saved mockup [{style}] -> {out_path} ({size_kb} KB)")
            mockup_paths[style] = out_path
        else:
            print(f"  ✗ Failed to generate [{style}] mockup for {cid}")

        time.sleep(1)

    return mockup_paths


def main():
    if not os.path.exists(MANIFEST_PATH):
        print(f"ERROR: {MANIFEST_PATH} not found. Run designer.py first.")
        return

    with open(MANIFEST_PATH, "r") as f:
        designs = json.load(f)

    if not designs:
        print("Manifest is empty. No designs to process.")
        return

    print(f"Generating 3D AI mockups for {len(designs)} designs in manifest...\n")

    updated = False
    for idx, d in enumerate(designs, 1):
        print(f"[{idx}/{len(designs)}] {d.get('title')} ({d.get('character')})")
        mockups = generate_mockups_for_design(d, styles=["floating_3d"])
        if mockups:
            d["mockup_files"] = mockups
            updated = True

    if updated:
        with open(MANIFEST_PATH, "w") as f:
            json.dump(designs, f, indent=2)
        print(f"\nManifest updated with mockup filepaths at {MANIFEST_PATH}")

    print("\nMockup generation finished.")


if __name__ == "__main__":
    main()
