import os
import requests
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("PRINTIFY_API_KEY")
headers = {"Authorization": f"Bearer {api_key}"}

# Bella+Canvas 3001 = "Unisex Heavy Cotton Tee", blueprint ID 6
blueprint_id = 6

response = requests.get(
    f"https://api.printify.com/v1/catalog/blueprints/{blueprint_id}/print_providers.json",
    headers=headers
)
providers = response.json()

print(f"Print providers available for blueprint {blueprint_id}:\n")
for p in providers:
    print(f"  - {p['title']} (Provider ID: {p['id']})")