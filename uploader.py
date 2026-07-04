import os
import base64
import json
import random
import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY     = os.getenv("PRINTIFY_API_KEY")
SHOP_ID     = os.getenv("PRINTIFY_SHOP_ID")
PROVIDER_ID = 29  # Monster Digital

HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}

DESIGNS_DIR   = "designs"
MANIFEST_PATH = os.path.join(DESIGNS_DIR, "manifest.json")

# Product types: 6 tees + 4 hoodies per batch of 10
BLUEPRINTS = {
    "tee":    {"id": 6,  "name": "Tee",    "price": 2299},
    "hoodie": {"id": 77, "name": "Hoodie", "price": 3999},
}

# Colors available for each blueprint (verified against Monster Digital)
COLORS = {
    "tee": [
        "Black", "White", "Navy", "Red", "Royal",
        "Sport Grey", "Maroon", "Forest Green",
        "Sand", "Light Blue",
    ],
    "hoodie": [
        "Black", "Navy", "Charcoal", "Forest Green",
        "Dark Heather", "Ash", "Carolina Blue",
        "Heather Navy", "Gold", "Maroon",
    ],
}

# Always include M + L, randomly add 2 more
CORE_SIZES     = {"m", "l"}
OPTIONAL_SIZES = ["s", "xl", "xs"]


def build_product_assignments(total):
    """6 tees + 4 hoodies, shuffled randomly."""
    n_hoodies = max(1, round(total * 0.4))
    n_tees    = total - n_hoodies
    types = ["tee"] * n_tees + ["hoodie"] * n_hoodies
    random.shuffle(types)
    return types


def get_variants(product_type):
    """Get 6 random colors × (M, L + 2 random sizes) for the given product type."""
    bp_id        = BLUEPRINTS[product_type]["id"]
    color_pool   = COLORS[product_type]
    chosen_colors = random.sample(color_pool, min(6, len(color_pool)))
    extra_sizes   = set(random.sample(OPTIONAL_SIZES, 2))
    active_sizes  = CORE_SIZES | extra_sizes

    r = requests.get(
        f"https://api.printify.com/v1/catalog/blueprints/{bp_id}/print_providers/{PROVIDER_ID}/variants.json",
        headers=HEADERS
    )
    r.raise_for_status()
    all_variants = r.json()["variants"]

    selected = []
    for v in all_variants:
        parts = v["title"].split("/")
        color = parts[0].strip() if len(parts) > 1 else v["title"].strip()
        size  = parts[1].strip().lower() if len(parts) > 1 else ""
        if (any(color.lower() == c.lower() for c in chosen_colors)
                and size in active_sizes):
            selected.append(v)

    print(f"  Colors: {', '.join(chosen_colors)}")
    print(f"  Sizes: {', '.join(sorted(active_sizes))}")
    print(f"  Variants selected: {len(selected)}")
    return selected


def upload_image(image_path):
    """Upload image to Printify media library, return image ID."""
    with open(image_path, "rb") as f:
        encoded = base64.b64encode(f.read()).decode("utf-8")
    r = requests.post(
        "https://api.printify.com/v1/uploads/images.json",
        headers=HEADERS,
        json={"file_name": os.path.basename(image_path), "contents": encoded}
    )
    r.raise_for_status()
    return r.json()["id"]


def build_print_areas(image_id, variant_ids, placement):
    """Front-only print. Scale adapts to placement intent."""
    p = placement.lower()
    if "waist" in p or "oversized" in p:
        scale = 0.95
    elif "small" in p or "left chest" in p:
        scale = 0.35
    elif "banner" in p or "horizontal" in p:
        scale = 0.85
    else:
        scale = 0.80

    return [{
        "variant_ids": variant_ids,
        "placeholders": [{
            "position": "front",
            "images": [{
                "id": image_id,
                "x": 0.5,
                "y": 0.5,
                "scale": scale,
                "angle": 0
            }]
        }]
    }]


def create_draft(image_id, variants, title, slogan, placement, product_type):
    """Create a draft product on Printify."""
    bp       = BLUEPRINTS[product_type]
    bp_id    = bp["id"]
    price    = bp["price"]
    type_label = bp["name"]

    variant_ids  = [v["id"] for v in variants]
    full_title   = f"{title} | {type_label}"
    description  = (
        f"{slogan} — Urban Vault original design. Premium quality {type_label.lower()}. Great gift idea."
        if slogan else
        f"Urban Vault original graphic {type_label.lower()}. Premium quality print. Great gift idea."
    )

    payload = {
        "title": full_title,
        "description": description,
        "blueprint_id": bp_id,
        "print_provider_id": PROVIDER_ID,
        "variants": [
            {"id": vid, "price": price, "is_enabled": True}
            for vid in variant_ids
        ],
        "print_areas": build_print_areas(image_id, variant_ids, placement)
    }

    r = requests.post(
        f"https://api.printify.com/v1/shops/{SHOP_ID}/products.json",
        headers=HEADERS,
        json=payload
    )

    if r.status_code not in (200, 201):
        print(f"  ERROR {r.status_code}: {r.text[:300]}")
        return None

    return r.json()


if __name__ == "__main__":
    if not os.path.exists(MANIFEST_PATH):
        print(f"ERROR: {MANIFEST_PATH} not found. Run designer.py first.")
        exit(1)

    with open(MANIFEST_PATH, "r") as f:
        designs = json.load(f)

    if not designs:
        print("No designs in manifest.")
        exit(0)

    assignments = build_product_assignments(len(designs))
    tee_count    = assignments.count("tee")
    hoodie_count = assignments.count("hoodie")
    print(f"Product plan: {tee_count} tees + {hoodie_count} hoodies\n")
    print(f"Uploading {len(designs)} designs to Printify...\n")

    created = 0

    for i, design in enumerate(designs):
        image_path   = os.path.join(DESIGNS_DIR, design["filename"])
        product_type = assignments[i]
        placement    = design.get("placement", "front center")

        if not os.path.exists(image_path):
            print(f"[{i+1}/{len(designs)}] SKIP — file not found: {image_path}")
            continue

        print(f"[{i+1}/{len(designs)}] {design['title']}")
        print(f"  Type: {BLUEPRINTS[product_type]['name']} (blueprint {BLUEPRINTS[product_type]['id']})")
        print(f"  Placement: {placement}")

        try:
            variants = get_variants(product_type)
            if not variants:
                print("  ERROR: no variants matched — skipping.")
                continue

            image_id = upload_image(image_path)
            product  = create_draft(
                image_id, variants,
                design["title"], design.get("slogan", ""),
                placement, product_type
            )

            if product:
                print(f"  Draft created. ID: {product['id']}")
                created += 1
            else:
                print(f"  Failed.")

        except Exception as e:
            print(f"  ERROR: {e}")

        print()

    print(f"Done. {created}/{len(designs)} drafts created.")
    print("Review and publish from your Printify dashboard.")