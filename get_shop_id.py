import os
import requests
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("PRINTIFY_API_KEY")

response = requests.get(
    "https://api.printify.com/v1/shops.json",
    headers={"Authorization": f"Bearer {api_key}"}
)

print(response.json())