import os
import base64
import json
import time
import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY     = os.getenv("PRINTIFY_API_KEY")
SHOP_ID     = os.getenv("PRINTIFY_SHOP_ID")
PROVIDER_ID = 29  # Monster Digital

if not API_KEY or not SHOP_ID:
    print("ERROR: Missing PRINTIFY_API_KEY or PRINTIFY_SHOP_ID in .env")
    exit(1)

HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}

DESIGNS_DIR   = "designs"
MANIFEST_PATH = os.path.join(DESIGNS_DIR, "manifest.json")
MOCKUPS_DIR   = os.path.join(DESIGNS_DIR, "mockups")

# 7 Monster Digital Blueprints (Prices in cents, ensuring >= 30% margin)
BLUEPRINTS = {
    "tee": {
        "id": 6,
        "name": "Heavy Cotton Tee",
        "price": 2299,
        "default_colors": ["Black", "Navy", "Charcoal", "Dark Heather", "Forest Green"]
    },
    "hoodie": {
        "id": 77,
        "name": "Heavy Blend™ Hoodie",
        "price": 3999,
        "default_colors": ["Black", "Navy", "Charcoal", "Dark Heather", "Forest Green"]
    },
    "crewneck": {
        "id": 49,
        "name": "Crewneck Sweatshirt",
        "price": 3499,
        "default_colors": ["Black", "Navy", "Dark Heather", "Charcoal", "Sport Grey"]
    },
    "tank": {
        "id": 39,
        "name": "Jersey Tank Top",
        "price": 1999,
        "default_colors": ["Black", "Navy"]
    },
    "long_sleeve": {
        "id": 41,
        "name": "Long Sleeve Tee",
        "price": 2799,
        "default_colors": ["Black", "Navy", "Dark Grey Heather", "Asphalt"]
    },
    "boxy_tee": {
        "id": 1382,
        "name": "Oversized Boxy Tee",
        "price": 2499,
        "default_colors": ["Black", "Dark Grey", "Navy"]
    },
    "tote_bag": {
        "id": 1313,
        "name": "Canvas Tote Bag",
        "price": 1499,
        "default_colors": ["Black", "Natural"]
    }
}

# Core streetwear apparel sizes
CORE_APPAREL_SIZES = {"s", "m", "l", "xl", "2xl"}


def get_target_colors(design, product_type):
    """Determine best colors for product based on design mode and blueprint availability."""
    bg_mode = design.get("bg_mode", "matched")
    bg_color = design.get("bg_color", "#000000").upper()
    bp_defaults = BLUEPRINTS[product_type]["default_colors"]

    if bg_mode == "matched":
        if bg_color == "#000000":
            return ["Black"]
        elif bg_color == "#1B2838":
            return ["Navy", "Black"]
        elif bg_color == "#36454F":
            return ["Dark Heather", "Charcoal", "Dark Grey", "Black"]
        else:
            return ["Black"]
    else:
        # Transparent mode: use design's shirt_colors or blueprint defaults
        return design.get("shirt_colors", bp_defaults[:3])


def get_variants(product_type, target_colors):
    """Retrieve matching variants from Printify catalog using robust options lookup."""
    bp_id = BLUEPRINTS[product_type]["id"]

    r = requests.get(
        f"https://api.printify.com/v1/catalog/blueprints/{bp_id}/print_providers/{PROVIDER_ID}/variants.json",
        headers=HEADERS,
        timeout=30
    )
    r.raise_for_status()
    all_variants = r.json().get("variants", [])

    selected = []
    target_lower = [c.lower() for c in target_colors]

    for v in all_variants:
        options = v.get("options", {})
        color = options.get("color", "").strip()
        size = options.get("size", "").strip().lower()

        # Fallback to title parsing if options dictionary is empty
        if not color or not size:
            title = v.get("title", "")
            if "/" in title:
                parts = [p.strip() for p in title.split("/")]
                if parts[0].lower() in ["s", "m", "l", "xl", "2xl", "3xl", "xs"]:
                    size, color = parts[0].lower(), parts[1]
                else:
                    color, size = parts[0], parts[1].lower()

        # Check color match
        if any(t in color.lower() for t in target_lower):
            # Check size match
            if product_type == "tote_bag":
                selected.append(v)
            elif size in CORE_APPAREL_SIZES:
                selected.append(v)

    # Fallback: if no variant matched target colors, pick first available color in core sizes
    if not selected:
        for v in all_variants:
            size = v.get("options", {}).get("size", "").strip().lower()
            if size in CORE_APPAREL_SIZES or product_type == "tote_bag":
                selected.append(v)
                if len(selected) >= 5:
                    break

    return selected


def upload_image_to_printify(image_path):
    """Upload image to Printify media library, returns image ID."""
    with open(image_path, "rb") as f:
        encoded = base64.b64encode(f.read()).decode("utf-8")
    
    payload = {
        "file_name": os.path.basename(image_path),
        "contents": encoded
    }
    r = requests.post(
        "https://api.printify.com/v1/uploads/images.json",
        headers=HEADERS,
        json=payload,
        timeout=60
    )
    r.raise_for_status()
    return r.json()["id"]


def build_print_areas(image_id, variant_ids, placement, product_type):
    """Build front print area configuration with proper scaling for product type."""
    p = placement.lower()
    if product_type == "tote_bag":
        scale = 0.70
        y = 0.55
    elif "waist" in p or "oversized" in p or product_type == "boxy_tee":
        scale = 0.90
        y = 0.50
    elif "small" in p or "left chest" in p:
        scale = 0.35
        y = 0.30
    elif product_type == "hoodie":
        scale = 0.78
        y = 0.56  # slightly lower to clear pocket
    else:
        scale = 0.82
        y = 0.50

    return [{
        "variant_ids": variant_ids,
        "placeholders": [{
            "position": "front",
            "images": [{
                "id": image_id,
                "x": 0.5,
                "y": y,
                "scale": scale,
                "angle": 0
            }]
        }]
    }]


def create_product_draft(design, product_type, image_id, variants):
    """Create a draft product on Printify with full KAGE tags and character branding."""
    bp = BLUEPRINTS[product_type]
    bp_id = bp["id"]
    price = bp["price"]
    type_label = bp["name"]

    character = design.get("character", "KAGE Character")
    character_tag = design.get("character_tag", "")
    niche = design.get("niche", "streetwear")
    niche_tag = design.get("niche_tag", f"niche:{niche}")
    title = design.get("title", "KAGE Graphic")
    full_title = f"{title} | {type_label}"

    variant_ids = [v["id"] for v in variants]

    # Description crafted in KAGE brand voice
    description = (
        f"<p><strong>{full_title}</strong> // KAGE Character Drop</p>\n"
        f"<p>From the shadows of Neo-Tokyo. Featuring original <strong>{character}</strong> artwork "
        f"engineered for the KAGE streetwear line.</p>\n"
        f"<ul>\n"
        f"  <li><strong>Brand:</strong> KAGE (\"WEAR THE SHADOW\")</li>\n"
        f"  <li><strong>Collection:</strong> {character} Collection</li>\n"
        f"  <li><strong>Fit:</strong> Premium relaxed streetwear silhouette</li>\n"
        f"  <li><strong>Print:</strong> High-density direct-to-garment (DTG) print with crisp edge definition</li>\n"
        f"  <li><strong>Fulfillment:</strong> Printed on demand by Monster Digital</li>\n"
        f"</ul>\n"
        f"<p><em>Wear the shadow. Own the character.</em></p>"
    )

    # Standardized tags for Shopify automated collections
    tags = [
        "KAGE",
        "wear-the-shadow",
        character,
        character_tag,
        niche,
        niche_tag,
        product_type,
        type_label
    ]
    # Clean out empty tags
    tags = [t for t in tags if t]

    payload = {
        "title": full_title,
        "description": description,
        "blueprint_id": bp_id,
        "print_provider_id": PROVIDER_ID,
        "tags": tags,
        "variants": [
            {"id": vid, "price": price, "is_enabled": True}
            for vid in variant_ids
        ],
        "print_areas": build_print_areas(image_id, variant_ids, design.get("placement", "front center"), product_type)
    }

    r = requests.post(
        f"https://api.printify.com/v1/shops/{SHOP_ID}/products.json",
        headers=HEADERS,
        json=payload,
        timeout=45
    )

    if r.status_code not in (200, 201):
        print(f"    ✗ ERROR {r.status_code}: {r.text[:300]}")
        return None

    return r.json()


def get_existing_product_titles():
    """Fetch existing product titles in shop to prevent duplicates."""
    titles = set()
    page = 1
    while True:
        url = f"https://api.printify.com/v1/shops/{SHOP_ID}/products.json?page={page}&limit=50"
        r = requests.get(url, headers=HEADERS, timeout=20)
        if r.status_code != 200:
            break
        data = r.json()
        prods = data.get("data", [])
        if not prods:
            break
        for p in prods:
            titles.add(p.get("title"))
        if len(prods) < 50 or page >= data.get("last_page", 1):
            break
        page += 1
    return titles


def upload_mockup_if_available(design):
    """Upload custom 3D mockup to Printify media library if it exists."""
    cid = design.get("id", "")
    mockup_path = os.path.join(MOCKUPS_DIR, f"{cid}_floating_3d.jpg")
    
    if os.path.exists(mockup_path) and os.path.getsize(mockup_path) > 5000:
        try:
            mockup_id = upload_image_to_printify(mockup_path)
            print(f"    ✓ 3D Mockup uploaded to Printify Media Library (ID: {mockup_id})")
            return mockup_id
        except Exception as e:
            print(f"    ⚠ Could not upload mockup image: {e}")
    return None


def main():
    if not os.path.exists(MANIFEST_PATH):
        print(f"ERROR: {MANIFEST_PATH} not found. Run designer.py first.")
        return

    with open(MANIFEST_PATH, "r") as f:
        designs = json.load(f)

    if not designs:
        print("Manifest is empty.")
        return

    print(f"Starting KAGE Multi-Product Upload to Printify (Shop ID: {SHOP_ID})...\n")

    existing_titles = get_existing_product_titles()
    print(f"Found {len(existing_titles)} existing products currently in Printify shop.\n")

    total_created = 0

    for i, design in enumerate(designs, 1):
        image_path = os.path.join(DESIGNS_DIR, design.get("filename", ""))
        cid = design.get("id", f"design_{i}")
        character = design.get("character", "Unknown")
        title = design.get("title", "")

        if not os.path.exists(image_path):
            print(f"[{i}/{len(designs)}] SKIP {cid} — image file not found: {image_path}")
            continue

        print(f"[{i}/{len(designs)}] Processing {title} ({character})")

        # Upload print file to Printify
        try:
            print(f"  Uploading print art ({os.path.basename(image_path)})...")
            image_id = upload_image_to_printify(image_path)
            print(f"  ✓ Print art uploaded. Image ID: {image_id}")
        except Exception as e:
            print(f"  ✗ Failed to upload print file: {e}")
            continue

        # Upload custom 3D mockup if present
        upload_mockup_if_available(design)

        # Get assigned product types (e.g. tee, hoodie, boxy_tee)
        assigned_types = design.get("product_types", ["tee", "hoodie"])
        print(f"  Creating {len(assigned_types)} products: {', '.join(assigned_types)}")

        for ptype in assigned_types:
            if ptype not in BLUEPRINTS:
                print(f"    ⚠ Skipping unknown product type: {ptype}")
                continue

            bp = BLUEPRINTS[ptype]
            type_label = bp["name"]
            full_title = f"{title} | {type_label}"

            if full_title in existing_titles:
                print(f"    ✓ Product already exists: '{full_title}' — skipping.")
                continue

            target_colors = get_target_colors(design, ptype)
            variants = get_variants(ptype, target_colors)

            if not variants:
                print(f"    ✗ No variants found for {ptype} in colors {target_colors} — skipping.")
                continue

            print(f"    Creating {type_label} ({len(variants)} variants in {target_colors})...")
            product = create_product_draft(design, ptype, image_id, variants)

            if product:
                pid = product.get("id")
                print(f"    ✓ Draft created: {pid} | {product.get('title')}")
                existing_titles.add(full_title)
                total_created += 1
            else:
                print(f"    ✗ Failed to create {ptype} draft.")

            time.sleep(1)  # Rate limiting between product creations

        print()

    print(f"Upload run complete. Created {total_created} draft products on Printify.")
    print("Ready for Shopify collection tagging & publishing.")


if __name__ == "__main__":
    main()