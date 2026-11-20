#!/bin/bash
# KAGE Growth Engine — one command. Builds any missing packs (free once backdrops are cached), opens the dashboard.
cd "$(dirname "$0")/.." || exit 1
venv/bin/python machine/kage.py packs --max-images 0
venv/bin/python machine/kage.py status
(sleep 2 && open http://127.0.0.1:8765) &
exec venv/bin/python machine/kage.py dashboard
