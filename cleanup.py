import os
import time
import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("PRINTIFY_API_KEY")
SHOP_ID = os.getenv("PRINTIFY_SHOP_ID")

if not API_KEY or not SHOP_ID:
    print("ERROR: Missing PRINTIFY_API_KEY or PRINTIFY_SHOP_ID in .env")
    exit(1)

HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}

def get_all_products():
    """Retrieve all products in the Printify shop with pagination support."""
    products = []
    page = 1
    while True:
        url = f"https://api.printify.com/v1/shops/{SHOP_ID}/products.json?page={page}&limit=50"
        r = requests.get(url, headers=HEADERS)
        if r.status_code != 200:
            print(f"Error fetching products (page {page}): {r.status_code} {r.text}")
            break
        data = r.json()
        current_batch = data.get("data", [])
        if not current_batch:
            break
        products.extend(current_batch)
        if len(current_batch) < 50 or page >= data.get("last_page", 1):
            break
        page += 1
    return products

def delete_product(product_id, title):
    """Delete a product from Printify."""
    url = f"https://api.printify.com/v1/shops/{SHOP_ID}/products/{product_id}.json"
    r = requests.delete(url, headers=HEADERS)
    if r.status_code in (200, 204):
        print(f"  ✓ Deleted: [{product_id}] {title}")
        return True
    else:
        print(f"  ✗ Failed to delete [{product_id}] {title}: HTTP {r.status_code} - {r.text}")
        return False

def main():
    print(f"Connecting to Printify Shop: {SHOP_ID}...")
    products = get_all_products()
    print(f"Found {len(products)} products on Printify.\n")

    if not products:
        print("Shop is already clean. No products to delete.")
        return

    deleted_count = 0
    for idx, p in enumerate(products, 1):
        pid = p.get("id")
        title = p.get("title", "Untitled")
        print(f"[{idx}/{len(products)}] Deleting product {pid}...")
        if delete_product(pid, title):
            deleted_count += 1
        time.sleep(0.5)  # Be gentle with Printify rate limits

    print(f"\nCleanup complete. Successfully deleted {deleted_count}/{len(products)} products.")

if __name__ == "__main__":
    main()
