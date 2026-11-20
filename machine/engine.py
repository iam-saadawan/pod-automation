"""KAGE Growth Engine — content-pack generation.

For every quality-passed design in designs/manifest.json this produces, under
machine/out/<design_id>/ :
  scene_1.jpg, scene_2.jpg   Pollinations (flux) lifestyle scenes   [costs pollen]
  pin_*.jpg                  1000x1500 Pinterest pins (PIL typography, free)
  video.mp4                  9:16 slideshow with music (ffmpeg, free)
  copy.json                  hook / captions / hashtags / pin copy (Gemini, template fallback)
  status.json                approval state used by the dashboard

Pollinations spend is metered in machine/ledger.json and capped (default 16
images/run) because the balance is small.
"""
import json
import os
import random
import subprocess
import time
from io import BytesIO
from pathlib import Path
from urllib.parse import quote

import requests
from PIL import Image, ImageDraw, ImageFont, ImageFilter

ROOT = Path(__file__).resolve().parent.parent
OUT = Path(__file__).resolve().parent / "out"
LEDGER = Path(__file__).resolve().parent / "ledger.json"
MANIFEST = ROOT / "designs" / "manifest.json"
SONGS = Path.home() / "MoneyPrinterTurbo" / "resource" / "songs"
STORE_URL = "https://jmxvzh-87.myshopify.com"

# Very small IP blocklist — rules.md #1. Copy is rejected if it names any of these.
IP_BLOCKLIST = ["naruto", "goku", "pokemon", "pikachu", "nike", "adidas", "supreme", "mario",
                "zelda", "one piece", "demon slayer", "jjk", "ghibli", "marvel", "dc comics",
                "toyota", "nissan", "honda", "ae86", "gtr", "skyline"]


def load_env():
    env = {}
    p = ROOT / ".env"
    if p.exists():
        for line in p.read_text().splitlines():
            if "=" in line and not line.strip().startswith("#"):
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip().strip('"').strip("'")
    for k in ("POLLINATIONS_API_KEY", "GEMINI_API_KEY"):
        env.setdefault(k, os.environ.get(k, ""))
    return env


ENV = load_env()


# ── ledger (spend guard) ─────────────────────────────────────────────
def ledger():
    if LEDGER.exists():
        return json.loads(LEDGER.read_text())
    return {"images_generated": 0, "failures": 0, "history": []}


def ledger_add(kind, ok):
    l = ledger()
    l["images_generated" if ok else "failures"] += 1
    l["history"].append({"t": time.strftime("%Y-%m-%dT%H:%M:%S"), "kind": kind, "ok": ok})
    l["history"] = l["history"][-200:]
    LEDGER.write_text(json.dumps(l, indent=2))


# ── Pollinations ─────────────────────────────────────────────────────
def pollinations_image(prompt, width=1024, height=1820, retries=2):
    """Generate one image with Pollinations flux. Returns PIL image or None."""
    url = f"https://gen.pollinations.ai/image/{quote(prompt)}?model=flux&width={width}&height={height}&nologo=true&seed={random.randint(1, 10**6)}"
    headers = {"Authorization": f"Bearer {ENV['POLLINATIONS_API_KEY']}"} if ENV.get("POLLINATIONS_API_KEY") else {}
    for attempt in range(retries + 1):
        try:
            r = requests.get(url, headers=headers, timeout=150)
            if r.status_code == 200 and len(r.content) > 5000:
                ledger_add("scene", True)
                return Image.open(BytesIO(r.content)).convert("RGB")
            print(f"    pollinations {r.status_code}: {r.text[:120]!r}")
            if r.status_code in (402, 403):  # out of pollen / forbidden — don't hammer
                break
        except Exception as e:  # network hiccup: retry
            print(f"    pollinations error: {e}")
        time.sleep(4 * (attempt + 1))
    ledger_add("scene", False)
    return None


# Backdrops only: never show apparel/prints here. Image models invent prints, and
# marketing must show the product the customer will actually receive (the real mockup
# is composited on top in collect_sources).
SCENE_STYLES = [
    ("street", "empty rain-soaked neon alley at night in a futuristic Asian megacity, reflections on wet asphalt, "
               "cinematic, moody, volumetric fog, no people, no text, no logos, no clothing"),
    ("void", "dark concrete studio wall with a single crimson rim light and drifting smoke, minimal, premium "
             "brand campaign backdrop, empty center, no people, no text, no logos, no clothing"),
]


BACKDROPS = Path(__file__).resolve().parent / "backdrops"


def make_scenes(design, out_dir, budget):
    """Backdrops are design-agnostic, so they live in a shared pool (generated once, reused
    by every design) — Pollinations pollen is only spent to top the pool up."""
    BACKDROPS.mkdir(exist_ok=True)
    for i, (name, tpl) in enumerate(SCENE_STYLES, 1):
        path = BACKDROPS / f"{name}.jpg"
        if path.exists() or budget["left"] <= 0:
            continue
        budget["left"] -= 1
        img = pollinations_image(tpl)
        if img:
            img.save(path, quality=92)
    pool = sorted(BACKDROPS.glob("*.jpg"))
    return pool[:2]


# ── copy ─────────────────────────────────────────────────────────────
def template_copy(design):
    ch = design.get("character", "KAGE")
    return {
        "hook": f"Some people walk in the light. {ch} doesn't.",
        "tiktok_caption": f"{ch} — from the KAGE shadow collection. Wear the shadow. #streetwear #darkaesthetic #techwear #kage",
        "instagram_caption": f"{ch}. Limited shadow drop. Link in bio. #streetwear #darkstreetwear #techwear #kage",
        "pin_title": f"{design.get('title', ch)} — dark streetwear",
        "pin_description": f"Dark, character-driven streetwear from KAGE. {ch}. Heavyweight cotton, printed on demand. Wear the shadow.",
        "cta": "WEAR THE SHADOW — kage store",
        "source": "template",
    }


def _cortex_key(name):
    p = Path.home() / "cortex-bots" / ".env"
    if p.exists():
        for line in p.read_text().splitlines():
            if line.startswith(name + "="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    return os.environ.get(name, "")


def _llm_json(prompt):
    """Groq (gpt-oss-20b, same brain cortex uses) first, Gemini second. Returns dict or None."""
    gk = _cortex_key("GROQ_API_KEY")
    if gk:
        try:
            r = requests.post("https://api.groq.com/openai/v1/chat/completions",
                              headers={"Authorization": f"Bearer {gk}"},
                              json={"model": "openai/gpt-oss-20b", "max_tokens": 2500, "reasoning_effort": "low",
                                    "response_format": {"type": "json_object"},
                                    "messages": [{"role": "user", "content": prompt}]}, timeout=60)
            return json.loads(r.json()["choices"][0]["message"]["content"])
        except Exception as e:
            print(f"    groq copy failed ({e})")
    key = ENV.get("GEMINI_API_KEY")
    if key:
        try:
            r = requests.post("https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent",
                              headers={"x-goog-api-key": key},
                              json={"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"responseMimeType": "application/json"}}, timeout=60)
            return json.loads(r.json()["candidates"][0]["content"]["parts"][0]["text"])
        except Exception as e:
            print(f"    gemini copy failed ({e})")
    return None


def make_copy(design):
    fallback = template_copy(design)
    prompt = (
        "You write short-form marketing copy for KAGE, a dark streetwear brand (tagline WEAR THE SHADOW). "
        f"Product character: {design.get('character')}; niche: {design.get('niche')}; title: {design.get('title')}. "
        "Voice: deadpan, dark, minimal. NEVER mention any real brand, anime, game, celebrity or song. "
        "Return STRICT JSON with keys hook (max 9 words, scroll-stopping), tiktok_caption (<=150 chars + 4 hashtags), "
        "instagram_caption (<=200 chars + 5 hashtags), pin_title (<=80 chars), pin_description (<=300 chars, SEO keywords), "
        "cta (<=6 words)."
    )
    data = _llm_json(prompt)
    if isinstance(data, list) and data:
        data = data[0]
    if not isinstance(data, dict):
        return fallback
    if any(w in json.dumps(data).lower() for w in IP_BLOCKLIST):
        print("    copy failed IP blocklist — using template")
        return fallback
    data["source"] = "llm"
    return {**fallback, **{k: v for k, v in data.items() if isinstance(v, str) and v.strip()}}


# ── typography ───────────────────────────────────────────────────────
def font(size):
    for p in ("/System/Library/Fonts/Supplemental/Impact.ttf", "/System/Library/Fonts/Helvetica.ttc",
              "/System/Library/Fonts/Supplemental/Arial Bold.ttf"):
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                pass
    return ImageFont.load_default()


def wrap(draw, text, fnt, max_w):
    lines, cur = [], ""
    for w in text.split():
        t = f"{cur} {w}".strip()
        if draw.textlength(t, font=fnt) <= max_w:
            cur = t
        else:
            lines.append(cur)
            cur = w
    return lines + [cur] if cur else lines


def cover(img, w, h):
    r = max(w / img.width, h / img.height)
    img = img.resize((int(img.width * r) + 1, int(img.height * r) + 1), Image.LANCZOS)
    x, y = (img.width - w) // 2, (img.height - h) // 2
    return img.crop((x, y, x + w, y + h))


def overlay_text(base, text, w, h, position="bottom", size=88, accent="#FFD23F"):
    img = cover(base, w, h).convert("RGBA")
    shade = Image.new("RGBA", img.size, (0, 0, 0, 0))
    sd = ImageDraw.Draw(shade)
    band_h = int(h * 0.36)
    y0 = h - band_h if position == "bottom" else 0
    for i in range(band_h):  # gradient scrim for legibility
        a = int(200 * (i / band_h if position == "bottom" else 1 - i / band_h))
        sd.line([(0, y0 + i), (w, y0 + i)], fill=(8, 10, 16, a))
    img = Image.alpha_composite(img, shade)
    d = ImageDraw.Draw(img)
    fnt = font(size)
    lines = wrap(d, text.upper(), fnt, w - 140)
    total = len(lines) * (size + 10)
    y = (h - total - 150) if position == "bottom" else 150
    for ln in lines:
        tw = d.textlength(ln, font=fnt)
        d.text(((w - tw) / 2 + 3, y + 3), ln, font=fnt, fill=(0, 0, 0, 255))
        d.text(((w - tw) / 2, y), ln, font=fnt, fill=(246, 241, 231, 255))
        y += size + 10
    tag = font(38)
    d.text((70, h - 90), "KAGE  //  WEAR THE SHADOW", font=tag, fill=accent)
    return img.convert("RGB")


# ── pins & video ─────────────────────────────────────────────────────
def composite_product(backdrop_path, mockup_path, out_path):
    """Real product mockup on an atmospheric backdrop (honest: shows the actual print)."""
    W, H = 1080, 1920
    bg = cover(Image.open(backdrop_path).convert("RGB"), W, H).filter(ImageFilter.GaussianBlur(2))
    m = Image.open(mockup_path).convert("RGB")
    mw = int(W * 0.92)
    m = m.resize((mw, int(m.height * mw / m.width)), Image.LANCZOS)
    mask = Image.new("L", m.size, 255).filter(ImageFilter.GaussianBlur(1))
    edge = Image.new("L", m.size, 0)
    ImageDraw.Draw(edge).rounded_rectangle((0, 0, m.width - 1, m.height - 1), 36, fill=255)
    bg.paste(m, ((W - m.width) // 2, (H - m.height) // 2 - 60), edge)
    bg.save(out_path, quality=92)
    return out_path


def collect_sources(design, scenes, out_dir=None):
    mocks = [ROOT / rel for rel in design.get("mockup_files", {}).values() if (ROOT / rel).exists()]
    srcs = list(mocks)  # real product first
    if mocks and out_dir is not None:
        for i, sc in enumerate(scenes, 1):
            srcs.append(composite_product(sc, mocks[0], out_dir / f"composite_{i}.jpg"))
    elif not mocks:
        srcs += list(scenes)
    return srcs


def make_pins(design, copy, sources, out_dir):
    pins = []
    for i, s in enumerate(sources[:3], 1):
        img = overlay_text(Image.open(s), copy["pin_title"].split("—")[0].strip(), 1000, 1500, "bottom", 76)
        p = out_dir / f"pin_{i}.jpg"
        img.save(p, quality=90)
        pins.append(p)
    return pins


def make_video(design, copy, sources, out_dir):
    if not sources:
        return None
    W, H, SEC = 1080, 1920, 3
    slides = []
    for i, s in enumerate(sources[:4]):
        text = copy["hook"] if i == 0 else (copy["cta"] if i == len(sources[:4]) - 1 else "")
        img = overlay_text(Image.open(s), text, W, H, "bottom", 84) if text else cover(Image.open(s).convert("RGB"), W, H)
        sp = out_dir / f"_slide_{i}.jpg"
        img.save(sp, quality=92)
        slides.append(sp)
    songs = sorted(SONGS.glob("*.mp3")) if SONGS.exists() else []
    inputs, filters = [], []
    for i, sp in enumerate(slides):
        inputs += ["-i", str(sp)]  # single frame: zoompan emits d frames per input frame
        zoom = "min(zoom+0.0009,1.12)"
        filters.append(f"[{i}:v]scale=1188:2112,zoompan=z='{zoom}':d={SEC*30}:s={W}x{H}:fps=30,setsar=1,format=yuv420p[v{i}]")
    n = len(slides)
    chain, last = "", "v0"
    for i in range(1, n):  # crossfade
        chain += f"[{last}][v{i}]xfade=transition=fade:duration=0.5:offset={i*(SEC-0.5)}[x{i}];"
        last = f"x{i}"
    fc = ";".join(filters) + ";" + chain.rstrip(";") if n > 1 else ";".join(filters)
    cmd = ["ffmpeg", "-y", "-loglevel", "error", *inputs]
    if songs:
        cmd += ["-stream_loop", "-1", "-i", str(random.choice(songs))]
    cmd += ["-filter_complex", fc, "-map", f"[{last}]"]
    if songs:
        cmd += ["-map", f"{n}:a", "-af", "volume=0.6,afade=t=out:st=%d:d=1" % max(1, n * SEC - 2), "-c:a", "aac", "-shortest"]
    cmd += ["-c:v", "libx264", "-preset", "veryfast", "-crf", "22", "-pix_fmt", "yuv420p", str(out_dir / "video.mp4")]
    r = subprocess.run(cmd, capture_output=True, text=True)
    for sp in slides:
        sp.unlink(missing_ok=True)
    if r.returncode != 0:
        print("    ffmpeg failed:", r.stderr[-400:])
        return None
    return out_dir / "video.mp4"


# ── orchestration ────────────────────────────────────────────────────
def build_pack(design, budget, force=False):
    did = design["id"]
    out_dir = OUT / did
    out_dir.mkdir(parents=True, exist_ok=True)
    if (out_dir / "status.json").exists() and not force:
        print(f"  {did}: pack exists — skip (use --force)")
        return
    print(f"  {did}: scenes…")
    scenes = make_scenes(design, out_dir, budget)
    print(f"  {did}: copy…")
    copy = make_copy(design)
    (out_dir / "copy.json").write_text(json.dumps(copy, indent=2))
    sources = collect_sources(design, scenes, out_dir)
    print(f"  {did}: pins + video from {len(sources)} sources…")
    pins = make_pins(design, copy, sources, out_dir)
    video = make_video(design, copy, sources, out_dir)
    (out_dir / "status.json").write_text(json.dumps({
        "design_id": did, "title": design.get("title"), "character": design.get("character"),
        "niche": design.get("niche"), "pins": [p.name for p in pins], "video": video.name if video else None,
        "approved": {"pinterest": False, "tiktok": False, "instagram": False, "youtube": False},
        "posted": {}, "built_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }, indent=2))


def build_all(max_images=16, only=None, force=False):
    designs = [d for d in json.loads(MANIFEST.read_text()) if d.get("quality_passed", True)]
    if only:
        designs = [d for d in designs if d["id"] in only]
    budget = {"left": max_images}
    print(f"Building packs for {len(designs)} designs (image budget {max_images})")
    for d in designs:
        build_pack(d, budget, force)
    print("Ledger:", {k: v for k, v in ledger().items() if k != "history"})
