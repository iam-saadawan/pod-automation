import os
import requests
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.getenv("PRINTIFY_API_KEY")
SHOP_ID = os.getenv("PRINTIFY_SHOP_ID")

HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}

def get_all_products():
    url = f"https://api.printify.com/v1/shops/{SHOP_ID}/products.json"
    products = []
    # Simplified without pagination handling for now, assuming < 100 products.
    # The default limit is 100 which is more than 19.
    r = requests.get(url, headers=HEADERS)
    if r.status_code == 200:
        data = r.json()
        return data.get("data", [])
    else:
        print(f"Error fetching products: {r.status_code}")
        return []

def unpublish_product(product_id):
    url = f"https://api.printify.com/v1/shops/{SHOP_ID}/products/{product_id}/unpublish.json"
    r = requests.post(url, headers=HEADERS)
    if r.status_code in (200, 201):
        print(f"Unpublished {product_id}")
    else:
        print(f"Failed to unpublish {product_id}: {r.status_code} {r.text}")

def main():
    products = get_all_products()
    print(f"Found {len(products)} products. Unpublishing them all...")
    for p in products:
        unpublish_product(p["id"])
    print("Done!")

if __name__ == "__main__":
    main()
