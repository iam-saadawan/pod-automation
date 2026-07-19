import os
import json
import time
# pyrefly: ignore [missing-import]
import numpy as np
import requests
from io import BytesIO
from urllib.parse import quote
# pyrefly: ignore [missing-import]
from PIL import Image, ImageDraw, ImageFont
# pyrefly: ignore [missing-import]
from rembg import remove, new_session
# pyrefly: ignore [missing-import]
from dotenv import load_dotenv

load_dotenv()

POLLINATIONS_API_KEY = os.getenv("POLLINATIONS_API_KEY")
OUTPUT_DIR = "designs"

# ── rembg session (loaded once, reused for all designs) ──────────────────────
# isnet-general-use has noticeably better edge detection than default u2net
REMBG_SESSION = new_session("isnet-general-use")


def build_full_prompt(concept):
    """Build a Flux prompt using the master prompt template structure.

    Structure (from SKILL_BIBLE_print_on_demand.md):
      [STYLE] → [SUBJECT] → [COMPOSITION] → [COLOR] → [LINE/EDGE] → [NEGATIVE]

    The image_prompt from research.py already follows this structure, so we
    reinforce the critical technical parts and strip anything contradictory.
    """
    base = concept["image_prompt"]

    # NEVER ask Flux to render text — it can't do it well.
    # Text designs get their slogans composited via Pillow after generation.
    text_block = (
        "This is a pure graphic illustration — absolutely no text, no words, "
        "no letters, no numbers, no typography anywhere in the image."
    )

    # Reinforced technical requirements (the non-negotiable rembg-survival kit)
    # Banning grey smudges, shading, face shadows, and textures directly fixes Flux artifacts.
    tech_block = (
        "isolated on solid pure white #FFFFFF background, "
        "centered composition, single cohesive graphic, "
        "generous margin around artwork, nothing touching canvas edges, "
        "screen-print style, thick bold black outlines, flat solid color fills, "
        "hard clean edges, no gradients, no glow, no drop shadow, no soft airbrush, "
        "no shading, no gray smudges, no dirty textures, no realistic face shadows, "
        "100% solid flat shapes, no smoke, no mist, no particles, no haze, "
        "no watermark, no signature, no mockup, no t-shirt rendering, "
        "no photo realism, no photography, no 3D render, "
        "print-ready vector-style artwork."
    )

    return f"{base} {text_block} {tech_block}"


def generate_image(concept):
    """Generate image via Pollinations Flux.

    Uses portrait orientation (closer to 4500x5400 print ratio) and higher
    resolution where possible.
    """
    full_prompt = build_full_prompt(concept)
    encoded = quote(full_prompt)

    # Portrait orientation: 1536x2048 is closer to the 4500x5400 print ratio
    # than 2048x2048 square. Gives us a better starting point for upscaling.
    placement = concept.get("placement", "front center")
    if "left chest" in placement or "small" in placement:
        # Small logo designs can stay square
        width, height = 1536, 1536
    else:
        # Large prints → portrait to match tee print area ratio (5:6)
        width, height = 1536, 1840

    url = (
        f"https://gen.pollinations.ai/image/{encoded}"
        f"?model=flux&width={width}&height={height}&nologo=true&key={POLLINATIONS_API_KEY}"
    )

    response = requests.get(url, timeout=120)

    if response.status_code != 200:
        print(f"  ERROR ({response.status_code}): {response.text[:200]}")
        return None

    if len(response.content) < 5000:
        print(f"  ERROR: response too small ({len(response.content)} bytes) — likely an error message")
        return None

    return response.content


def remove_background(image_bytes):
    """Strip background using isnet-general-use model without alpha matting.

    Returns a PIL Image with transparent background, or None on failure.
    """
    img = Image.open(BytesIO(image_bytes)).convert("RGBA")

    # Disable alpha matting for clean vector/cartoon art on solid white background.
    # This avoids matrix solver failures and preserves fine line details.
    result = remove(
        img,
        session=REMBG_SESSION,
        alpha_matting=False,
    )

    return result


def cleanup_white_halo(img, erode_px=0):
    """Remove the white halo/fringe that rembg often leaves at edges.

    Erodes the alpha channel by `erode_px` pixels to eat into the fringe,
    then checks for remaining semi-transparent pixels with high brightness
    (white halo artifacts) and cleans them.
    """
    arr = np.array(img)
    alpha = arr[:, :, 3]

    # Erode alpha mask by erode_px to remove fringe
    if erode_px > 0:
        # pyrefly: ignore [missing-import]
        from PIL import ImageFilter
        alpha_img = Image.fromarray(alpha, mode="L")
        for _ in range(erode_px):
            alpha_img = alpha_img.filter(ImageFilter.MinFilter(3))
        arr[:, :, 3] = np.array(alpha_img)

    # Kill semi-transparent pixels that are very bright (white halo remnants)
    # These are pixels where alpha is 1-254 AND RGB brightness > 240
    semi_mask = (arr[:, :, 3] > 0) & (arr[:, :, 3] < 255)
    brightness = arr[:, :, :3].mean(axis=2)
    halo_mask = semi_mask & (brightness > 240)
    arr[halo_mask, 3] = 0  # Make white halo pixels fully transparent

    return Image.fromarray(arr)


def check_quality(img, placement="front center"):
    """Basic quality check after background removal.

    Returns (passed: bool, issues: list[str]).
    Flags designs that may need manual review.
    """
    arr = np.array(img)
    alpha = arr[:, :, 3]
    total_px = alpha.size
    issues = []

    # Check: too many semi-transparent pixels (sign of failed removal)
    # With alpha_matting=False, we raise the threshold slightly to allow natural anti-aliased outlines.
    semi_transparent = ((alpha > 10) & (alpha < 245)).sum()
    semi_pct = semi_transparent / total_px * 100
    if semi_pct > 15:
        issues.append(f"High semi-transparent pixel count ({semi_pct:.1f}%) — rembg may have struggled")

    # Check: too little content (design got mostly erased)
    # Pocket/chest logos naturally have very small opaque pixel percentages.
    opaque = (alpha > 245).sum()
    opaque_pct = opaque / total_px * 100
    min_opaque = 1.0 if any(k in placement.lower() for k in ["chest", "logo", "small"]) else 4.0
    if opaque_pct < min_opaque:
        issues.append(f"Very little content remaining ({opaque_pct:.1f}% opaque) — design may be destroyed")

    # Check: content touching edges (bad composition)
    edge_alpha = np.concatenate([alpha[0, :], alpha[-1, :], alpha[:, 0], alpha[:, -1]])
    edge_opaque = (edge_alpha > 128).sum()
    if edge_opaque > 20:
        issues.append(f"Content touching canvas edges ({edge_opaque} edge pixels opaque)")

    return len(issues) == 0, issues


if __name__ == "__main__":
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    with open("niches.json", "r") as f:
        data = json.load(f)

    concepts = data["concepts"]
    niche = data.get("niche", "unknown niche")
    print(f"Generating {len(concepts)} designs for niche: '{niche}'\n")

    results = []
    flagged = []

    for i, concept in enumerate(concepts, 1):
        filename = f"design_{i:02d}.png"
        output_path = os.path.join(OUTPUT_DIR, filename)

        print(f"[{i}/{len(concepts)}] {concept['title']}")
        print(f"  Style: {concept.get('style', '')[:65]}...")
        print(f"  Placement: {concept.get('placement', 'front center')}")
        has_text = concept.get("has_text", False)
        slogan = concept.get("slogan", "")
        print(f"  Text: {'\"' + slogan + '\"' if has_text and slogan else '(graphic only)'}")

        image_bytes = generate_image(concept)

        if image_bytes is None:
            print(f"  SKIPPED — generation failed.")
            time.sleep(2)
            continue

        try:
            # Step 1: Remove background
            print(f"  Removing background (isnet-general-use + alpha matting)...")
            result = remove_background(image_bytes)

            if result is None:
                print(f"  SKIPPED — background removal failed.")
                time.sleep(2)
                continue

            # Step 2: Clean up white halo
            print(f"  Cleaning up white halo...")
            result = cleanup_white_halo(result, erode_px=0)

            # Step 3: Quality check
            passed, issues = check_quality(result, concept.get("placement", "front center"))
            if not passed:
                print(f"  ⚠ QUALITY WARNING:")
                for issue in issues:
                    print(f"    • {issue}")
                flagged.append(filename)
            else:
                print(f"  ✓ Quality check passed")

            # Save the design
            result.save(output_path, "PNG")
            size_kb = os.path.getsize(output_path) // 1024
            print(f"  Saved -> {output_path} ({size_kb} KB, transparent PNG)")

            results.append({
                "filename": filename,
                "title": concept["title"],
                "slogan": slogan,
                "has_text": has_text,
                "placement": concept.get("placement", "front center"),
                "quality_passed": passed,
            })

        except Exception as e:
            print(f"  ERROR: {e}")

        time.sleep(2)

    # Save manifest
    with open(os.path.join(OUTPUT_DIR, "manifest.json"), "w") as f:
        json.dump(results, f, indent=2)

    print(f"\nDone. {len(results)}/{len(concepts)} images saved.")
    if flagged:
        print(f"\n⚠ {len(flagged)} designs flagged for manual review:")
        for fn in flagged:
            print(f"  • {fn}")
    print(f"Manifest: {OUTPUT_DIR}/manifest.json")