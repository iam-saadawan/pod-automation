import requests
from urllib.parse import quote

prompt = "A cute chibi cat isolated on solid white background, centered cohesive graphic, screen-print style, thick black outlines, flat color fills, clean edges, no gradients, no shading, no smudges, no realistic shadows, print-ready vector-style artwork."
encoded = quote(prompt)
url = f"https://gen.pollinations.ai/image/{encoded}?model=flux&width=1536&height=1536&nologo=true"
res = requests.get(url)
print(res.status_code)
