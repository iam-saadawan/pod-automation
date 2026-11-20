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

r = requests.get(f"https://api.printify.com/v1/shops/{SHOP_ID}/products.json", headers=HEADERS)
products = r.json().get("data", [])
print(f"Total products: {len(products)}")
for p in products[:5]:
    print(p.get("id"), p.get("title"))
