#!/usr/bin/env python3
"""KAGE Growth Engine CLI.

  kage.py packs [--max-images N] [--only id1,id2] [--force]   build content packs
  kage.py drafts                                             upload designs to Printify as DRAFTS (unpublished)
  kage.py dashboard [--port 8765]                            approval + auth dashboard
  kage.py status                                             connection + pack summary
"""
import argparse
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import engine  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("packs")
    p.add_argument("--max-images", type=int, default=16)
    p.add_argument("--only", default="")
    p.add_argument("--force", action="store_true")
    sub.add_parser("drafts")
    d = sub.add_parser("dashboard")
    d.add_argument("--port", type=int, default=8765)
    sub.add_parser("status")
    sub.add_parser("queue")
    sub.add_parser("metrics")
    a = ap.parse_args()

    if a.cmd == "packs":
        engine.build_all(a.max_images, [x for x in a.only.split(",") if x], a.force)
    elif a.cmd == "drafts":
        subprocess.run([sys.executable, str(engine.ROOT / "uploader.py")], cwd=engine.ROOT, check=True)
    elif a.cmd == "dashboard":
        import dashboard
        dashboard.serve(a.port)
    elif a.cmd == "queue":
        import queue_export
        queue_export.export()
    elif a.cmd == "metrics":
        import metrics
        metrics.main()
    elif a.cmd == "status":
        import dashboard
        for k, v in dashboard.connections().items():
            print(f"{k:12} {'OK ' if v['ok'] else '-- '} {v['detail']}")


if __name__ == "__main__":
    main()
