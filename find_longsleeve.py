import os, requests
from dotenv import load_dotenv
load_dotenv()

headers = {"Authorization": f"Bearer {os.getenv('PRINTIFY_API_KEY')}"}
blueprints = requests.get("https://api.printify.com/v1/catalog/blueprints.json", headers=headers).json()

for b in blueprints:
    if "long sleeve" in b["title"].lower():
        print(f"{b['title']} (ID: {b['id']})")