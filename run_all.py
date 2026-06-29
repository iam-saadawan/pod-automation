"""
run_all.py

The master conductor for the AI POD automation pipeline.
Runs, in order:
  1. research.py  -> generates niche/design concepts via Gemini, saves niches.json
  2. designer.py  -> generates actual images via Pollinations Flux, saves designs/*.jpg + manifest.json
  3. uploader.py  -> uploads all images to Printify as DRAFT products

This is the single script the Linux cron job calls every night.
It does NOT publish anything live — every product lands as a draft for manual review.
"""

import subprocess
import sys
import datetime

SCRIPTS = ["research.py", "designer.py", "uploader.py"]


def run_script(script_name):
    print(f"\n{'='*60}")
    print(f"RUNNING: {script_name}")
    print(f"{'='*60}\n")

    result = subprocess.run(
        [sys.executable, script_name],
        capture_output=False
    )

    if result.returncode != 0:
        print(f"\n!!! {script_name} exited with error code {result.returncode}. Stopping pipeline. !!!")
        return False

    return True


if __name__ == "__main__":
    start_time = datetime.datetime.now()
    print(f"Pipeline started at {start_time.strftime('%Y-%m-%d %H:%M:%S')}")

    for script in SCRIPTS:
        success = run_script(script)
        if not success:
            print(f"\nPipeline halted. Fix the error in {script} before re-running.")
            sys.exit(1)

    end_time = datetime.datetime.now()
    duration = (end_time - start_time).total_seconds()

    print(f"\n{'='*60}")
    print(f"PIPELINE COMPLETE in {duration:.1f} seconds")
    print(f"Go check your Printify dashboard for new draft products.")
    print(f"{'='*60}")