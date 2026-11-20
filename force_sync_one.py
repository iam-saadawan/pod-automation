import os, requests, dotenv
dotenv.load_dotenv()
API_KEY = os.getenv('PRINTIFY_API_KEY')
SHOP_ID = os.getenv('PRINTIFY_SHOP_ID')
HEADERS = {'Authorization': f'Bearer {API_KEY}', 'Content-Type': 'application/json'}

# The Road Warrior hoodie ID
product_id = "6a491f17c35bd7acda0c0603"

r = requests.get(f'https://api.printify.com/v1/shops/{SHOP_ID}/products/{product_id}.json', headers=HEADERS)
product = r.json()

# Append a space to the description to force a diff
desc = product.get("description", "")
if not desc.endswith(" "):
    desc += " "
else:
    desc = desc.strip()

# Update the product in Printify
# To update, we must send blueprint_id, print_provider_id, variants, print_areas, etc.
# Wait, updating a product requires a massive payload. 
# Let's try just triggering the publish again first.
