"""
remove_bg.py

Standalone background remover for manually generated design images.
Use this when you're NOT running the full pipeline (e.g. designs made
manually via Gemini/chat.google.com) and just need to strip the
background and get a transparent PNG ready for uploader.py.

Uses isnet-general-use model (better edges than default u2net),
alpha matting for cleaner transitions, and white halo cleanup.

USAGE:
    Single file:
        python3 remove_bg.py path/to/image.png

    Whole folder (processes every .png/.jpg/.jpeg inside):
        python3 remove_bg.py path/to/folder

Output:
    Saves alongside the original as <original_name>_transparent.png
"""

import sys
import os
# pyrefly: ignore [missing-import]
import numpy as np
from io import BytesIO
# pyrefly: ignore [missing-import]
from PIL import Image, ImageFilter
# pyrefly: ignore [missing-import]
from rembg import remove, new_session

# Load the better model once
SESSION = new_session("isnet-general-use")


def cleanup_white_halo(img, erode_px=0):
    """Remove white halo/fringe left by rembg at edges."""
    arr = np.array(img)
    alpha = arr[:, :, 3]

    # Erode alpha mask to eat the halo fringe
    if erode_px > 0:
        alpha_img = Image.fromarray(alpha, mode="L")
        for _ in range(erode_px):
            alpha_img = alpha_img.filter(ImageFilter.MinFilter(3))
        arr[:, :, 3] = np.array(alpha_img)

    # Kill semi-transparent pixels that are very bright (white halo remnants)
    semi_mask = (arr[:, :, 3] > 0) & (arr[:, :, 3] < 255)
    brightness = arr[:, :, :3].mean(axis=2)
    halo_mask = semi_mask & (brightness > 240)
    arr[halo_mask, 3] = 0

    return Image.fromarray(arr)


def process_file(input_path):
    if not os.path.exists(input_path):
        print(f"  SKIP — file not found: {input_path}")
        return

    name, _ext = os.path.splitext(input_path)
    output_path = f"{name}_transparent.png"

    print(f"Processing: {input_path}")
    with open(input_path, "rb") as f:
        img = Image.open(BytesIO(f.read())).convert("RGBA")

    # Remove background with isnet-general-use without alpha matting
    print(f"  Removing background (isnet-general-use)...")
    result = remove(
        img,
        session=SESSION,
        alpha_matting=False,
    )

    # Clean up white halo
    print(f"  Cleaning up white halo...")
    result = cleanup_white_halo(result, erode_px=0)

    result.save(output_path, "PNG")

    size_kb = os.path.getsize(output_path) // 1024
    print(f"  Saved -> {output_path} ({size_kb} KB, transparent PNG)\n")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 remove_bg.py <image_file_or_folder>")
        sys.exit(1)

    target = sys.argv[1]

    if os.path.isdir(target):
        exts = (".png", ".jpg", ".jpeg")
        files = [
            os.path.join(target, f) for f in sorted(os.listdir(target))
            if f.lower().endswith(exts) and not f.lower().endswith("_transparent.png")
        ]
        if not files:
            print(f"No image files found in {target}")
            sys.exit(0)
        print(f"Found {len(files)} image(s) to process.\n")
        for f in files:
            process_file(f)
    elif os.path.isfile(target):
        process_file(target)
    else:
        print(f"ERROR: {target} is not a valid file or folder.")
        sys.exit(1)

    print("Done.")