"""Hand KAGE packs to cortex's approval queues (~/.automaton/control/queue).
Queue-only: cortex treats these as awaiting approval; nothing is posted here."""
import json, shutil, time
from pathlib import Path
import engine

Q = Path.home() / ".automaton" / "control" / "queue"


def export():
    (Q / "pinterest-pins").mkdir(parents=True, exist_ok=True)
    (Q / "tiktok-videos").mkdir(parents=True, exist_ok=True)
    n_pin = n_vid = 0
    for d in sorted(engine.OUT.iterdir()):
        sp = d / "status.json"
        if not sp.exists():
            continue
        s, c = json.loads(sp.read_text()), json.loads((d / "copy.json").read_text())
        for pin in s["pins"]:
            f = Q / "pinterest-pins" / f"pin_kage_{d.name}_{pin[:-4]}.json"
            if f.exists():
                continue
            shutil.copy(d / pin, Q / "pinterest-pins" / f"kage_{d.name}_{pin}")
            f.write_text(json.dumps({"title": c["pin_title"], "description": c["pin_description"], "alt_text": c["pin_title"],
                                     "link": engine.STORE_URL, "image_file": f"kage_{d.name}_{pin}", "network": "kage",
                                     "keyword": s["niche"], "generatedAt": time.strftime("%Y-%m-%dT%H:%M:%S"), "stream": "kage-growth-engine"}, indent=2))
            n_pin += 1
        v = d / (s.get("video") or "")
        dst = Q / "tiktok-videos" / f"kage_{d.name}.mp4"
        if s.get("video") and not dst.exists():
            shutil.copy(v, dst)
            dst.with_suffix(".json").write_text(json.dumps({"caption": c["tiktok_caption"], "hook": c["hook"], "stream": "kage-growth-engine"}, indent=2))
            n_vid += 1
    print(f"queued {n_pin} pins, {n_vid} videos -> {Q}")


if __name__ == "__main__":
    export()
