import os, requests, dotenv, time
dotenv.load_dotenv()
API_KEY = os.getenv('PRINTIFY_API_KEY')
SHOP_ID = os.getenv('PRINTIFY_SHOP_ID')
HEADERS = {'Authorization': f'Bearer {API_KEY}', 'Content-Type': 'application/json'}

r = requests.get(f'https://api.printify.com/v1/shops/{SHOP_ID}/products.json', headers=HEADERS)
products = r.json().get('data', [])

drafts = [p for p in products if not p.get('external')]

print(f"Found {len(drafts)} unpublished drafts out of {len(products)} total products.")

payload = {
  "title": True,
  "description": True,
  "images": True,
  "variants": True,
  "tags": True,
  "keyFeatures": True,
  "shipping_template": True
}

for d in drafts:
    print(f"Publishing: {d.get('title')}")
    url = f"https://api.printify.com/v1/shops/{SHOP_ID}/products/{d['id']}/publish.json"
    res = requests.post(url, headers=HEADERS, json=payload)
    if res.status_code in (200, 201):
        print("  -> Success")
    else:
        print(f"  -> Error: {res.status_code} {res.text}")
    time.sleep(1) # Be nice to the API

print("Finished publishing.")
