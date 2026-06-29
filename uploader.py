import os
import base64
import json
import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("PRINTIFY_API_KEY")
SHOP_ID = os.getenv("PRINTIFY_SHOP_ID")
BLUEPRINT_ID = int(os.getenv("BLUEPRINT_ID"))
PRINT_PROVIDER_ID = int(os.getenv("PRINT_PROVIDER_ID"))

HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}

DESIGNS_DIR = "designs"
MANIFEST_PATH = os.path.join(DESIGNS_DIR, "manifest.json")


def upload_image(image_path):
    """Upload a local image file to Printify's media library and return its image ID."""
    with open(image_path, "rb") as f:
        encoded = base64.b64encode(f.read()).decode("utf-8")

    response = requests.post(
        "https://api.printify.com/v1/uploads/images.json",
        headers=HEADERS,
        json={
            "file_name": os.path.basename(image_path),
            "contents": encoded
        }
    )
    response.raise_for_status()
    return response.json()["id"]


def get_variants():
    """Fetch available variants (sizes/colors) for this blueprint + provider combo.
    Selects up to 6 popular colors (one Medium-size variant each) to stay within
    eBay's monthly selling limit, which counts every variant against your quota."""

    PREFERRED_COLORS = ["Black", "White", "Navy", "Sport Grey", "Maroon", "Royal"]

    response = requests.get(
        f"https://api.printify.com/v1/catalog/blueprints/{BLUEPRINT_ID}/print_providers/{PRINT_PROVIDER_ID}/variants.json",
        headers=HEADERS
    )
    response.raise_for_status()
    all_variants = response.json()["variants"]

    # Group by color, picking one size per color (preferring Medium)
    by_color = {}
    for v in all_variants:
        parts = v["title"].split("/")
        color = parts[0].strip() if len(parts) > 1 else v["title"].strip()
        size_part = parts[1].strip() if len(parts) > 1 else ""

        if color not in by_color:
            by_color[color] = v
        elif size_part.lower() in ("m", "medium"):
            by_color[color] = v

    # Now filter down to just our preferred colors, in that order
    selected = []
    for preferred in PREFERRED_COLORS:
        for color_name, variant in by_color.items():
            if preferred.lower() == color_name.lower():
                selected.append(variant)
                break

    if not selected:
        print(f"  WARNING: none of the preferred colors matched. Falling back to first 6 available.")
        selected = list(by_color.values())[:6]

    print(f"  Selected {len(selected)} color variants: {', '.join(v['title'] for v in selected)}")
    return selected


def create_draft_product(image_id, variants, title, slogan):
    """Create a draft product on Printify using the uploaded image."""

    selected_variant_ids = [v["id"] for v in variants]

    description = f"{slogan} — a print-on-demand design from Urban Vault." if slogan else \
                  f"A unique design from Urban Vault."

    payload = {
        "title": title,
        "description": description,
        "blueprint_id": BLUEPRINT_ID,
        "print_provider_id": PRINT_PROVIDER_ID,
        "variants": [
            {"id": vid, "price": 2499, "is_enabled": True}
            for vid in selected_variant_ids
        ],
        "print_areas": [
            {
                "variant_ids": selected_variant_ids,
                "placeholders": [
                    {
                        "position": "front",
                        "images": [
                            {
                                "id": image_id,
                                "x": 0.5,
                                "y": 0.5,
                                "scale": 0.8,
                                "angle": 0
                            }
                        ]
                    }
                ]
            }
        ]
    }

    response = requests.post(
        f"https://api.printify.com/v1/shops/{SHOP_ID}/products.json",
        headers=HEADERS,
        json=payload
    )

    if response.status_code not in (200, 201):
        print(f"  ERROR creating product: {response.status_code} {response.text[:200]}")
        return None

    return response.json()


if __name__ == "__main__":
    if not os.path.exists(MANIFEST_PATH):
        print(f"ERROR: {MANIFEST_PATH} not found. Run designer.py first.")
        exit(1)

    with open(MANIFEST_PATH, "r") as f:
        designs = json.load(f)

    if not designs:
        print("No designs found in manifest. Nothing to upload.")
        exit(0)

    print(f"Fetching variants for blueprint {BLUEPRINT_ID} / provider {PRINT_PROVIDER_ID}...")
    variants = get_variants()
    print(f"Using {len(variants)} color variants for each product.\n")

    print(f"Uploading {len(designs)} designs to Printify as drafts...\n")

    created_count = 0

    for i, design in enumerate(designs, 1):
        image_path = os.path.join(DESIGNS_DIR, design["filename"])

        if not os.path.exists(image_path):
            print(f"[{i}/{len(designs)}] SKIP - file not found: {image_path}")
            continue

        print(f"[{i}/{len(designs)}] {design['title']}")

        try:
            image_id = upload_image(image_path)
            product = create_draft_product(image_id, variants, design["title"], design["slogan"])

            if product:
                print(f"  Created draft. Product ID: {product['id']}")
                created_count += 1
            else:
                print(f"  Failed to create draft.")
        except Exception as e:
            print(f"  ERROR: {e}")

    print(f"\nDone. {created_count}/{len(designs)} draft products created.")
    print("Go check your Printify dashboard to review and publish.")