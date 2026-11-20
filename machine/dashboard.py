"""KAGE Growth Engine dashboard (stdlib only). http://127.0.0.1:8765

Nothing here posts or publishes on its own: every outward action is a button
that the operator clicks (Printify->Shopify publish, Pinterest post).
"""
import base64
import html
import json
import mimetypes
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

import requests

import engine

OUT = engine.OUT
CORTEX_ENV = Path.home() / "cortex-bots" / ".env"
TIKTOK_LOGIN = Path.home() / "MoneyPrinterTurbo" / "tiktok_login.py"


def cortex_env():
    env = {}
    if CORTEX_ENV.exists():
        for line in CORTEX_ENV.read_text().splitlines():
            if "=" in line and not line.strip().startswith("#"):
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip().strip('"').strip("'")
    return env


def _real(v):
    return bool(v) and not re.search(r"your_|placeholder|xxx|changeme", v, re.I)


def connections():
    """Read-only health checks. Never prints secrets."""
    e, c = engine.ENV, cortex_env()
    res = {}
    res["Pollinations"] = {"ok": _real(e.get("POLLINATIONS_API_KEY")), "detail": "key present (%d images generated tonight)" % engine.ledger()["images_generated"], "fix": ""}
    try:
        r = requests.get("https://generativelanguage.googleapis.com/v1beta/models", headers={"x-goog-api-key": e.get("GEMINI_API_KEY", "")}, timeout=15)
        res["Gemini"] = {"ok": r.status_code == 200, "detail": "live" if r.status_code == 200 else f"HTTP {r.status_code}: key rejected (copy uses Groq instead)",
                         "fix": "aistudio.google.com/apikey → create a key starting 'AIza…' → pod-automation/.env GEMINI_API_KEY"}
    except Exception as ex:
        res["Gemini"] = {"ok": False, "detail": str(ex)[:80], "fix": ""}
    try:
        r = requests.get(f"https://api.printify.com/v1/shops.json", headers={"Authorization": f"Bearer {e.get('PRINTIFY_API_KEY','')}"}, timeout=15)
        names = [s["title"] for s in r.json()] if r.status_code == 200 else []
        res["Printify"] = {"ok": r.status_code == 200, "detail": f"shops: {', '.join(names)}" if names else f"HTTP {r.status_code}", "fix": "Printify → Account → Connections → API tokens; put in pod-automation/.env"}
    except Exception as ex:
        res["Printify"] = {"ok": False, "detail": str(ex)[:80], "fix": ""}
    try:
        r = requests.get("https://api.pinterest.com/v5/user_account", headers={"Authorization": f"Bearer {c.get('PINTEREST_ACCESS_TOKEN','')}"}, timeout=15)
        res["Pinterest"] = {"ok": r.status_code == 200, "detail": (r.json().get("username", "connected") if r.status_code == 200 else f"HTTP {r.status_code} (token expired/invalid)"),
                            "fix": "developers.pinterest.com → your app → generate access token (scopes pins:write boards:read) → cortex-bots/.env PINTEREST_ACCESS_TOKEN"}
    except Exception as ex:
        res["Pinterest"] = {"ok": False, "detail": str(ex)[:80], "fix": ""}
    try:
        r = requests.get(engine.STORE_URL, timeout=15, allow_redirects=True)
        res["Shopify store"] = {"ok": r.status_code == 200, "detail": f"HTTP {r.status_code} {engine.STORE_URL}", "fix": "Shopify trial expiry: check billing"}
    except Exception as ex:
        res["Shopify store"] = {"ok": False, "detail": str(ex)[:80], "fix": ""}
    res["TikTok"] = {"ok": TIKTOK_LOGIN.exists() and (Path.home() / "MoneyPrinterTurbo/storage/tiktok_session.json").exists(),
                     "detail": "session file found" if (Path.home() / "MoneyPrinterTurbo/storage/tiktok_session.json").exists() else "no saved session",
                     "fix": "Run: cd ~/MoneyPrinterTurbo && uv run python tiktok_login.py  (log in once in the browser window)"}
    res["Instagram"] = {"ok": _real(c.get("IG_ACCESS_TOKEN")) and _real(c.get("IG_USER_ID")), "detail": "token present (not live-verified)", "fix": "Meta developer app → IG Graph API token → cortex-bots/.env IG_ACCESS_TOKEN + IG_USER_ID"}
    res["YouTube"] = {"ok": _real(c.get("YOUTUBE_API_KEY")), "detail": "API key present; uploads go via Upload-Post in MoneyPrinterTurbo", "fix": "MoneyPrinterTurbo config.toml upload_post settings"}
    return res


def packs():
    out = []
    if OUT.exists():
        for d in sorted(OUT.iterdir()):
            sp = d / "status.json"
            if sp.exists():
                s = json.loads(sp.read_text())
                s["copy"] = json.loads((d / "copy.json").read_text()) if (d / "copy.json").exists() else {}
                out.append(s)
    return out


def save_status(s):
    s = {k: v for k, v in s.items() if k != "copy"}
    (OUT / s["design_id"] / "status.json").write_text(json.dumps(s, indent=2))


def printify_drafts():
    e = engine.ENV
    r = requests.get(f"https://api.printify.com/v1/shops/{e['PRINTIFY_SHOP_ID']}/products.json?limit=50",
                     headers={"Authorization": f"Bearer {e['PRINTIFY_API_KEY']}"}, timeout=30)
    return r.json().get("data", []) if r.status_code == 200 else []


def publish_product(pid):
    e = engine.ENV
    r = requests.post(f"https://api.printify.com/v1/shops/{e['PRINTIFY_SHOP_ID']}/products/{pid}/publish.json",
                      headers={"Authorization": f"Bearer {e['PRINTIFY_API_KEY']}"},
                      json={"title": True, "description": True, "images": True, "variants": True, "tags": True, "keyfeatures": True, "shipping_template": True}, timeout=30)
    return r.status_code, r.text[:200]


def post_pin(design_id, pin_name):
    c = cortex_env()
    s = json.loads((OUT / design_id / "status.json").read_text())
    copy = json.loads((OUT / design_id / "copy.json").read_text())
    b64 = base64.b64encode((OUT / design_id / pin_name).read_bytes()).decode()
    body = {"board_id": c.get("PINTEREST_BOARD_ID"), "title": copy["pin_title"][:100], "description": copy["pin_description"][:500],
            "link": engine.STORE_URL, "media_source": {"source_type": "image_base64", "content_type": "image/jpeg", "data": b64}}
    r = requests.post("https://api.pinterest.com/v5/pins", headers={"Authorization": f"Bearer {c.get('PINTEREST_ACCESS_TOKEN','')}"}, json=body, timeout=60)
    if r.status_code in (200, 201):
        s.setdefault("posted", {})["pinterest_" + pin_name] = r.json().get("id")
        save_status(s)
    return r.status_code, r.text[:200]


CSS = """body{background:#0D0F14;color:#F6F1E7;font-family:-apple-system,Helvetica,sans-serif;margin:0;padding:24px}
h1{letter-spacing:.2em;color:#FFD23F}h2{border-bottom:1px solid #2a2e38;padding-bottom:6px;margin-top:34px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:14px}
.card{background:#151923;border:1px solid #2a2e38;border-radius:10px;padding:12px}
.ok{color:#5ee08a}.bad{color:#ff6b6b}.muted{color:#9aa0ad;font-size:13px}
img,video{width:100%;border-radius:6px}.row{display:flex;gap:6px;flex-wrap:wrap;margin-top:8px}
button,a.b{background:#FFD23F;color:#0D0F14;border:0;border-radius:6px;padding:6px 10px;font-weight:700;cursor:pointer;text-decoration:none;font-size:13px}
button.g{background:#2a2e38;color:#F6F1E7}code{background:#222735;padding:2px 5px;border-radius:4px;font-size:12px}"""


def page():
    h = [f"<html><head><meta charset=utf-8><title>KAGE Growth Engine</title><style>{CSS}</style></head><body>",
         "<h1>KAGE GROWTH ENGINE</h1><div class=muted>Nothing posts or publishes until you click. Wear the shadow.</div>",
         "<h2>Connections</h2><div class=grid>"]
    for name, v in connections().items():
        h.append(f"<div class=card><b>{name}</b> <span class={'ok' if v['ok'] else 'bad'}>{'● connected' if v['ok'] else '● needs setup'}</span>"
                 f"<div class=muted>{html.escape(v['detail'])}</div>" + ("" if v["ok"] or not v["fix"] else f"<div class=muted>Fix: <code>{html.escape(v['fix'])}</code></div>") + "</div>")
    h.append("</div><h2>Printify products (drafts → Shopify)</h2><div class=grid>")
    for p in printify_drafts():
        # Printify's `visible` is True even for unpublished products; `external` only exists once pushed to Shopify.
        is_live = bool(p.get("external"))
        pub = "live on Shopify" if is_live else "draft (not on storefront)"
        h.append(f"<div class=card><b>{html.escape(p['title'][:60])}</b><div class=muted>{pub}</div>"
                 + ("" if is_live else f"<form method=post action='/publish?pid={p['id']}' onsubmit=\"return confirm('Publish to the LIVE Shopify store?')\"><div class=row><button>Publish to Shopify</button></div></form>") + "</div>")
    h.append("</div><h2>Content packs (approve → post)</h2>")
    for s in packs():
        did, cp = s["design_id"], s["copy"]
        h.append(f"<div class=card style='margin-bottom:14px'><b>{html.escape(str(s['title']))}</b> <span class=muted>{s['niche']} · {s['character']}</span>"
                 f"<div class=muted>Hook: {html.escape(cp.get('hook',''))}</div><div class=muted>TikTok: {html.escape(cp.get('tiktok_caption',''))}</div><div class=grid style='margin-top:8px'>")
        if s.get("video"):
            h.append(f"<div><video controls preload=metadata src='/file/{did}/{s['video']}'></video></div>")
        for pn in s["pins"]:
            posted = s.get("posted", {}).get("pinterest_" + pn)
            h.append(f"<div><img src='/file/{did}/{pn}'><div class=row>" + (f"<span class=ok>posted {posted}</span>" if posted else
                     f"<form method=post action='/pin?id={did}&pin={pn}' onsubmit=\"return confirm('Post this pin to Pinterest now?')\"><button>Post pin</button></form>") + "</div></div>")
        h.append("</div></div>")
    h.append("</body></html>")
    return "\n".join(h)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, body, ctype="text/html; charset=utf-8"):
        b = body if isinstance(body, bytes) else body.encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        u = urlparse(self.path)
        if u.path == "/":
            return self._send(200, page())
        if u.path == "/api/connections":
            return self._send(200, json.dumps(connections()), "application/json")
        if u.path.startswith("/file/"):
            parts = u.path.split("/")[2:]
            f = (OUT / Path(*parts)).resolve()
            if OUT.resolve() in f.parents and f.is_file():
                return self._send(200, f.read_bytes(), mimetypes.guess_type(str(f))[0] or "application/octet-stream")
        self._send(404, "not found")

    def do_POST(self):
        u, q = urlparse(self.path), parse_qs(urlparse(self.path).query)
        if u.path == "/publish":
            code, txt = publish_product(q["pid"][0])
        elif u.path == "/pin":
            code, txt = post_pin(q["id"][0], q["pin"][0])
        else:
            return self._send(404, "not found")
        self._send(200, f"<meta http-equiv=refresh content='4;url=/'><body style='background:#0D0F14;color:#F6F1E7;font-family:sans-serif;padding:30px'>HTTP {code}: {html.escape(txt)}<br>Returning…")


def serve(port=8765):
    # Bind loopback only: the dashboard can publish/post, so it must not be LAN-reachable.
    print(f"KAGE dashboard → http://127.0.0.1:{port}")
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()
