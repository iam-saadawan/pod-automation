import os
import requests
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("PRINTIFY_API_KEY")
headers = {"Authorization": f"Bearer {api_key}"}

response = requests.get(
    "https://api.printify.com/v1/catalog/blueprints/6/print_providers/29/variants.json",
    headers=headers
)
variants = response.json()["variants"]

colors = sorted(set(v["title"].split("/")[0].strip() for v in variants))
print(f"All {len(colors)} available colors for this shirt:\n")
for c in colors:
    print(f"  - {c}")