"""
upscale.py

Upscales transparent PNG designs to Monster Digital's required print specs:
  - Tee front: 4500 × 5400 px (≈300 DPI at 15" × 18")
  - PNG with transparency, sRGB

Runs after designer.py and before uploader.py in the pipeline.

METHODS (in order of quality):
  1. Real-ESRGAN (if installed) — AI upscaling, best quality, preserves sharp edges
  2. Pillow LANCZOS — high-quality traditional resampling, always available

USAGE:
    As part of pipeline (run_all.py calls this):
        python3 upscale.py

    Standalone on a single file:
        python3 upscale.py path/to/image.png

    Standalone on a folder:
        python3 upscale.py path/to/folder
"""

import sys
import os
import json
# pyrefly: ignore [missing-import]
from PIL import Image

DESIGNS_DIR = "designs"
MANIFEST_PATH = os.path.join(DESIGNS_DIR, "manifest.json")

# Monster Digital print specs
TARGET_WIDTH = 4500
TARGET_HEIGHT = 5400


def has_realesrgan():
    """Check if Real-ESRGAN is available."""
    try:
        # pyrefly: ignore [missing-import]
        from basicsr.archs.rrdbnet_arch import RRDBNet
        # pyrefly: ignore [missing-import]
        from realesrgan import RealESRGANer
        return True
    except ImportError:
        return False


def upscale_realesrgan(img):
    """Upscale using Real-ESRGAN (best quality, AI-based)."""
    # pyrefly: ignore [missing-import]
    import numpy as np
    # pyrefly: ignore [missing-import]
    from basicsr.archs.rrdbnet_arch import RRDBNet
    # pyrefly: ignore [missing-import]
    from realesrgan import RealESRGANer

    # Use RealESRGAN_x4plus for general upscaling
    model = RRDBNet(num_in_ch=3, num_out_ch=3, num_feat=64, num_block=23, num_grow_ch=32, scale=4)
    model_path = os.path.join(os.path.dirname(__file__), "weights", "RealESRGAN_x4plus.pth")

    if not os.path.exists(model_path):
        print("    Real-ESRGAN weights not found, falling back to Pillow...")
        return None

    upsampler = RealESRGANer(
        scale=4, model_path=model_path, model=model,
        tile=0, tile_pad=10, pre_pad=0, half=False
    )

    # Convert RGBA → process RGB and alpha separately
    arr = np.array(img)
    rgb = arr[:, :, :3]
    alpha = arr[:, :, 3]

    # Upscale RGB
    output_rgb, _ = upsampler.enhance(rgb, outscale=4)

    # Upscale alpha channel separately (as 3-channel grayscale)
    alpha_3ch = np.stack([alpha] * 3, axis=2)
    output_alpha_3ch, _ = upsampler.enhance(alpha_3ch, outscale=4)
    output_alpha = output_alpha_3ch[:, :, 0]

    # Recombine
    h, w = output_rgb.shape[:2]
    output = np.zeros((h, w, 4), dtype=np.uint8)
    output[:, :, :3] = output_rgb
    output[:, :, 3] = output_alpha

    return Image.fromarray(output)


def upscale_pillow(img, target_w, target_h):
    """Upscale using Pillow LANCZOS (always available, good quality)."""
    # Maintain aspect ratio: fit within target, then pad with transparency
    orig_w, orig_h = img.size
    ratio = min(target_w / orig_w, target_h / orig_h)
    new_w = int(orig_w * ratio)
    new_h = int(orig_h * ratio)

    # LANCZOS is the highest quality resampling filter in Pillow
    # pyrefly: ignore [missing-attribute]
    resized = img.resize((new_w, new_h), Image.LANCZOS)

    # Create target canvas with transparency and center the design
    canvas = Image.new("RGBA", (target_w, target_h), (0, 0, 0, 0))
    offset_x = (target_w - new_w) // 2
    offset_y = (target_h - new_h) // 2
    canvas.paste(resized, (offset_x, offset_y))

    return canvas


def upscale_image(input_path, output_path=None, use_ai=False):
    """Upscale a single image to print specs.

    Args:
        input_path: Path to the transparent PNG
        output_path: Where to save (defaults to overwriting input)
        use_ai: Whether to try Real-ESRGAN first
    """
    if output_path is None:
        output_path = input_path

    img = Image.open(input_path).convert("RGBA")
    orig_w, orig_h = img.size

    # Skip if already at or above target resolution
    if orig_w >= TARGET_WIDTH and orig_h >= TARGET_HEIGHT:
        print(f"    Already at target resolution ({orig_w}×{orig_h}), skipping.")
        return True

    result = None

    # Try Real-ESRGAN if requested and available
    if use_ai and has_realesrgan():
        print(f"    Upscaling with Real-ESRGAN (4x AI upscale)...")
        try:
            result = upscale_realesrgan(img)
            if result is not None:
                # Resize to exact target dims after AI upscale
                result = upscale_pillow(result, TARGET_WIDTH, TARGET_HEIGHT)
        except Exception as e:
            print(f"    Real-ESRGAN failed ({e}), falling back to Pillow...")
            result = None

    # Fallback: Pillow LANCZOS
    if result is None:
        print(f"    Upscaling with Pillow LANCZOS ({orig_w}×{orig_h} → {TARGET_WIDTH}×{TARGET_HEIGHT})...")
        result = upscale_pillow(img, TARGET_WIDTH, TARGET_HEIGHT)

    result.save(output_path, "PNG")
    size_kb = os.path.getsize(output_path) // 1024
    print(f"    Saved -> {output_path} ({size_kb} KB, {TARGET_WIDTH}×{TARGET_HEIGHT})")
    return True


if __name__ == "__main__":
    use_ai = has_realesrgan()
    if use_ai:
        print("Real-ESRGAN detected — using AI upscaling.\n")
    else:
        print("Real-ESRGAN not installed — using Pillow LANCZOS upscaling.")
        print("  (For better quality: pip install realesrgan basicsr)\n")

    # Mode 1: Standalone on file or folder
    if len(sys.argv) >= 2:
        target = sys.argv[1]
        if os.path.isfile(target):
            print(f"Upscaling: {target}")
            upscale_image(target, use_ai=use_ai)
        elif os.path.isdir(target):
            files = [
                os.path.join(target, f) for f in sorted(os.listdir(target))
                if f.lower().endswith(".png") and not f.startswith(".")
            ]
            print(f"Found {len(files)} PNG(s) to upscale.\n")
            for f in files:
                print(f"Upscaling: {os.path.basename(f)}")
                upscale_image(f, use_ai=use_ai)
                print()
        else:
            print(f"ERROR: {target} is not a valid file or folder.")
            sys.exit(1)
        print("Done.")
        sys.exit(0)

    # Mode 2: Pipeline mode — process designs from manifest
    if not os.path.exists(MANIFEST_PATH):
        print(f"ERROR: {MANIFEST_PATH} not found. Run designer.py first.")
        sys.exit(1)

    with open(MANIFEST_PATH, "r") as f:
        designs = json.load(f)

    if not designs:
        print("No designs in manifest.")
        sys.exit(0)

    print(f"Upscaling {len(designs)} designs to {TARGET_WIDTH}×{TARGET_HEIGHT}...\n")

    success = 0
    for i, design in enumerate(designs, 1):
        filepath = os.path.join(DESIGNS_DIR, design["filename"])
        if not os.path.exists(filepath):
            print(f"[{i}/{len(designs)}] SKIP — {design['filename']} not found")
            continue

        print(f"[{i}/{len(designs)}] {design['filename']}")
        if upscale_image(filepath, use_ai=use_ai):
            success += 1
        print()

    print(f"Done. {success}/{len(designs)} upscaled to print specs.")
