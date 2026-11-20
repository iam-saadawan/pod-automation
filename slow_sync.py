import os, requests, dotenv, time
dotenv.load_dotenv()
API_KEY = os.getenv('PRINTIFY_API_KEY')
SHOP_ID = os.getenv('PRINTIFY_SHOP_ID')
HEADERS = {'Authorization': f'Bearer {API_KEY}', 'Content-Type': 'application/json'}

r = requests.get(f'https://api.printify.com/v1/shops/{SHOP_ID}/products.json', headers=HEADERS)
products = r.json().get('data', [])

payload = {'title': True, 'description': True, 'images': True, 'variants': True, 'tags': True, 'keyFeatures': True, 'shipping_template': True}

print(f"Starting slow sync for {len(products)} products to avoid Shopify rate limits...")

for p in products:
    print(f"Processing: {p.get('title')}")
    pid = p['id']
    
    # 1. Unpublish to break the bad sync state
    requests.post(f'https://api.printify.com/v1/shops/{SHOP_ID}/products/{pid}/unpublish.json', headers=HEADERS)
    time.sleep(2)
    
    # 2. Fresh publish
    res = requests.post(f'https://api.printify.com/v1/shops/{SHOP_ID}/products/{pid}/publish.json', headers=HEADERS, json=payload)
    if res.status_code in (200, 201):
        print("  -> Success")
    else:
        print(f"  -> Error: {res.status_code}")
    
    # Wait 20 seconds to give Shopify time to download the 24 images before the next product
    time.sleep(20)

print("Finished slow sync.")
