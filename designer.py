import os
import json
import time
import numpy as np
import requests
from io import BytesIO
from urllib.parse import quote
from PIL import Image, ImageDraw, ImageFont
from dotenv import load_dotenv

load_dotenv()

POLLINATIONS_API_KEY = os.getenv("POLLINATIONS_API_KEY")
OUTPUT_DIR = "designs"

# Lazy-loaded rembg session (only initialized if transparent mode is used)
_REMBG_SESSION = None

def get_rembg_session():
    global _REMBG_SESSION
    if _REMBG_SESSION is None:
        from rembg import new_session
        print("  Initializing rembg session (isnet-general-use)...")
        _REMBG_SESSION = new_session("isnet-general-use")
    return _REMBG_SESSION


def build_full_prompt(concept):
    """Build a Flux prompt adapting dynamically to matched vs transparent mode.

    Structure:
      [BASE PROMPT] → [NEGATIVE/TEXT BLOCK] → [BACKGROUND/EDGE REINFORCEMENT]
    """
    base = concept.get("image_prompt", "")
    bg_mode = concept.get("bg_mode", "matched")
    bg_color = concept.get("bg_color", "#000000")

    # Anti-text rule — text is composited programmatically if needed
    text_block = "No text, no words, no letters, no typography, no watermark, no logo."

    if bg_mode == "matched":
        tech_block = (
            f"on solid {bg_color} background, the design fills the canvas edge to edge, "
            f"no border, no margin, seamless with {bg_color} background color, "
            f"dark streetwear aesthetic, high contrast, crisp line art, no t-shirt, no mockup, no photo realism."
        )
    else:
        tech_block = (
            "isolated on solid pure white background, centered cohesive graphic, "
            "screen-print style, thick black outlines, flat solid color fills, "
            "clean edges, no gradients, no shading, no smudges, "
            "no realistic shadows, print-ready vector-style artwork, no t-shirt, no mockup."
        )

    return f"{base} {text_block} {tech_block}".strip()


def generate_image(concept):
    """Generate image via Pollinations Flux API.

    Uses portrait orientation (1536x1840) to align with print area aspect ratio.
    """
    full_prompt = build_full_prompt(concept)
    encoded = quote(full_prompt)

    placement = concept.get("placement", "front center")
    if "left chest" in placement or "small" in placement:
        width, height = 1536, 1536
    else:
        width, height = 1536, 1840

    url = (
        f"https://gen.pollinations.ai/image/{encoded}"
        f"?model=flux&width={width}&height={height}&nologo=true"
    )
    if POLLINATIONS_API_KEY:
        url += f"&key={POLLINATIONS_API_KEY}"

    try:
        response = requests.get(url, timeout=120)
    except Exception as e:
        print(f"  ERROR calling Pollinations: {e}")
        return None

    if response.status_code != 200:
        print(f"  ERROR ({response.status_code}): {response.text[:200]}")
        return None

    if len(response.content) < 5000:
        print(f"  ERROR: response too small ({len(response.content)} bytes) — likely an error message")
        return None

    return response.content


def remove_background(image_bytes):
    """Strip background using isnet-general-use model without alpha matting for transparent mode."""
    from rembg import remove
    img = Image.open(BytesIO(image_bytes)).convert("RGBA")
    session = get_rembg_session()
    result = remove(
        img,
        session=session,
        alpha_matting=False,
    )
    return result


def cleanup_white_halo(img, erode_px=0):
    """Remove fringe artifacts from rembg transparent output."""
    arr = np.array(img)
    if arr.shape[2] < 4:
        return img

    if erode_px > 0:
        from PIL import ImageFilter
        alpha_img = Image.fromarray(arr[:, :, 3], mode="L")
        for _ in range(erode_px):
            alpha_img = alpha_img.filter(ImageFilter.MinFilter(3))
        arr[:, :, 3] = np.array(alpha_img)

    semi_mask = (arr[:, :, 3] > 0) & (arr[:, :, 3] < 255)
    brightness = arr[:, :, :3].mean(axis=2)
    halo_mask = semi_mask & (brightness > 240)
    arr[halo_mask, 3] = 0

    return Image.fromarray(arr)


def draw_slogan(img, slogan):
    """Draw slogan at bottom center if present."""
    if not slogan:
        return img
    
    draw = ImageDraw.Draw(img)
    width, height = img.size
    
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", int(width * 0.06))
    except:
        font = ImageFont.load_default()
        
    bbox = draw.textbbox((0, 0), slogan, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    
    x = (width - text_w) / 2
    y = height - text_h - int(height * 0.08)
    
    outline_w = max(2, int(width * 0.004))
    for dx in range(-outline_w, outline_w + 1):
        for dy in range(-outline_w, outline_w + 1):
            draw.text((x + dx, y + dy), slogan, font=font, fill=(0, 0, 0, 255))
            
    draw.text((x, y), slogan, font=font, fill=(255, 255, 255, 255))
    return img


def check_quality(img, bg_mode="matched", placement="front center"):
    """Check image quality according to design mode."""
    issues = []
    width, height = img.size

    if width < 1000 or height < 1000:
        issues.append(f"Low resolution ({width}x{height})")

    arr = np.array(img)

    if bg_mode == "matched":
        # Check that the image is not a completely blank solid color or blown out
        std_dev = arr[:, :, :3].std()
        if std_dev < 10.0:
            issues.append(f"Image has virtually no detail/variation (std: {std_dev:.2f})")
    else:
        # Transparent mode quality checks
        if arr.shape[2] == 4:
            alpha = arr[:, :, 3]
            total_px = alpha.size
            semi_transparent = ((alpha > 10) & (alpha < 245)).sum()
            semi_pct = semi_transparent / total_px * 100
            if semi_pct > 15:
                issues.append(f"High semi-transparent pixel count ({semi_pct:.1f}%)")

            opaque = (alpha > 245).sum()
            opaque_pct = opaque / total_px * 100
            min_opaque = 1.0 if any(k in placement.lower() for k in ["chest", "logo", "small"]) else 4.0
            if opaque_pct < min_opaque:
                issues.append(f"Very little content remaining ({opaque_pct:.1f}% opaque)")

    return len(issues) == 0, issues


if __name__ == "__main__":
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    with open("niches.json", "r") as f:
        data = json.load(f)

    concepts = data.get("concepts", [])
    brand = data.get("brand", "KAGE")
    tagline = data.get("tagline", "WEAR THE SHADOW")

    print(f"[{brand}] Generating {len(concepts)} character-driven designs...\n")

    results = []
    flagged = []

    for i, concept in enumerate(concepts, 1):
        cid = concept.get("id", f"concept_{i:02d}")
        filename = f"{cid}.png"
        output_path = os.path.join(OUTPUT_DIR, filename)

        bg_mode = concept.get("bg_mode", "matched")
        bg_color = concept.get("bg_color", "#000000")
        character = concept.get("character", "KAGE Entity")
        title = concept.get("title", f"Design {i}")

        print(f"[{i}/{len(concepts)}] {title}")
        print(f"  Character: {character} ({concept.get('character_tag', '')})")
        print(f"  Mode: {bg_mode.upper()} ({bg_color if bg_mode == 'matched' else 'Transparent'})")
        print(f"  Placement: {concept.get('placement', 'front center')}")

        image_bytes = generate_image(concept)

        if image_bytes is None:
            print(f"  SKIPPED — generation failed.")
            time.sleep(2)
            continue

        try:
            if bg_mode == "matched":
                print(f"  ✓ Matched mode: Preserving original background ({bg_color}) — skipping rembg.")
                img = Image.open(BytesIO(image_bytes)).convert("RGB")
            else:
                print(f"  Transparent mode: Stripping background via rembg...")
                img = remove_background(image_bytes)
                if img is None:
                    print(f"  SKIPPED — background removal failed.")
                    time.sleep(2)
                    continue
                img = cleanup_white_halo(img, erode_px=0)

            # Slogan overlay if requested
            slogan = concept.get("slogan", "")
            if concept.get("has_text", False) and slogan:
                print(f"  Drawing slogan: '{slogan}'")
                img = draw_slogan(img, slogan)

            # Quality verification
            passed, issues = check_quality(img, bg_mode=bg_mode, placement=concept.get("placement", "front center"))
            if not passed:
                print(f"  ⚠ QUALITY WARNING:")
                for issue in issues:
                    print(f"    • {issue}")
                flagged.append(filename)
            else:
                print(f"  ✓ Quality check passed")

            # Save design
            img.save(output_path, "PNG")
            size_kb = os.path.getsize(output_path) // 1024
            print(f"  Saved -> {output_path} ({size_kb} KB, {img.size[0]}x{img.size[1]})")

            results.append({
                "id": cid,
                "filename": filename,
                "title": title,
                "character": character,
                "character_tag": concept.get("character_tag", ""),
                "niche": concept.get("niche", ""),
                "niche_tag": concept.get("niche_tag", ""),
                "bg_mode": bg_mode,
                "bg_color": bg_color,
                "shirt_colors": concept.get("shirt_colors", ["Black"]),
                "product_types": concept.get("product_types", ["tee", "hoodie"]),
                "mockup_style": concept.get("mockup_style", "floating_3d"),
                "slogan": slogan,
                "has_text": concept.get("has_text", False),
                "placement": concept.get("placement", "front center"),
                "quality_passed": passed,
            })

        except Exception as e:
            print(f"  ERROR processing design {cid}: {e}")

        time.sleep(2)

    # Save manifest
    manifest_path = os.path.join(OUTPUT_DIR, "manifest.json")
    with open(manifest_path, "w") as f:
        json.dump(results, f, indent=2)

    print(f"\nDone. {len(results)}/{len(concepts)} designs saved to {OUTPUT_DIR}/")
    if flagged:
        print(f"⚠ {len(flagged)} designs flagged for review:")
        for fn in flagged:
            print(f"  • {fn}")
    print(f"Manifest written: {manifest_path}")