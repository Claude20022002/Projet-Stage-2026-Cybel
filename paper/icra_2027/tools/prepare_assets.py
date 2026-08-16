#!/usr/bin/env python3
"""Regenerate the two photographs in assets/ from the originals.

The paper does not name the institution or the robot model, so the robot
photograph has its identifying marks blurred: the logo band under the screen,
the institution name shown on the kiosk, and the on-screen QR code, which can
encode a URL. Re-run this script rather than editing the JPEGs by hand, so the
redaction stays reproducible and reviewable.

    python tools/prepare_assets.py

Adjust SOURCE_DIR if the originals move. Coordinates are in the cropped
frame; if you change a crop box, re-check the blur regions against it.
"""

from pathlib import Path

from PIL import Image, ImageEnhance, ImageFilter

SOURCE_DIR = Path(r"c:\Users\clusa\Desktop\redaction_latex\images")
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "assets"


def build_robot_photo() -> None:
    """Fig. 1 — robot with the reconstructed visitor interface on screen.

    The original is an underexposed phone frame at 720x1280. We upsample
    before sharpening, otherwise the unsharp mask puts halos on every edge.
    Redaction comes LAST: applied before sharpening, the mask redraws the very
    contours it is meant to hide.
    """
    image = Image.open(SOURCE_DIR / "cybel.jpeg").crop((160, 118, 545, 600)).convert("RGB")
    image = image.resize((image.width * 2, image.height * 2), Image.LANCZOS)

    image = ImageEnhance.Brightness(image).enhance(1.10)
    image = ImageEnhance.Contrast(image).enhance(1.18)
    image = ImageEnhance.Color(image).enhance(0.92)
    image = image.filter(ImageFilter.UnsharpMask(radius=2.2, percent=115, threshold=3))

    # Coordinates are in the upsampled frame (2x the crop above).
    redactions = [
        (206, 808, 540, 916),  # logo band beneath the touchscreen
        (316, 626, 436, 666),  # institution name, line under "Bienvenue dans"
        (526, 668, 604, 754),  # on-screen QR code
    ]
    for box in redactions:
        image.paste(image.crop(box).filter(ImageFilter.GaussianBlur(16)), box)

    image.save(OUTPUT_DIR / "robot_kiosk.jpg", quality=94, optimize=True, subsampling=0)
    print(f"assets/robot_kiosk.jpg {image.size} - {len(redactions)} regions redacted")


def build_vendor_map() -> None:
    """Fig. 5 — vendor deployment application and the laboratory map.

    Checked for identifying marks: none present, so no redaction is applied.
    """
    image = Image.open(SOURCE_DIR / "nouvellmap.jpeg").crop((30, 180, 1572, 1052))
    image = image.resize((image.width // 2, image.height // 2), Image.LANCZOS)
    image.save(OUTPUT_DIR / "vendor_map.jpg", quality=88, optimize=True)
    print(f"assets/vendor_map.jpg {image.size}")


if __name__ == "__main__":
    if not SOURCE_DIR.is_dir():
        raise SystemExit(f"Original images not found: {SOURCE_DIR}")
    OUTPUT_DIR.mkdir(exist_ok=True)
    build_robot_photo()
    build_vendor_map()
