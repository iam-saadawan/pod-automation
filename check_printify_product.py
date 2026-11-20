import os
import requests
from dotenv import load_dotenv
import json

load_dotenv()
API_KEY = os.getenv("PRINTIFY_API_KEY")
SHOP_ID = os.getenv("PRINTIFY_SHOP_ID")

HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}

r = requests.get(f"https://api.printify.com/v1/shops/{SHOP_ID}/products.json", headers=HEADERS)
products = r.json().get("data", [])
if not products:
    print("No products found")
else:
    # Get the latest one, which is likely the one the user just published
    latest = products[0]
    print(f"Product: {latest.get('title')}")
    print(f"Images count: {len(latest.get('images', []))}")
    if len(latest.get('images', [])) > 0:
        print(f"First image: {latest.get('images')[0]}")
    
