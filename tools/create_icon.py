#!/usr/bin/env python
"""Generate RepMark Studio branded PNG/ICO assets."""
from __future__ import annotations

from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"
PNG_PATH = ASSETS / "RepMark_RSS.png"
ICO_PATH = ASSETS / "RepMark_RSS.ico"


def font(size: int, bold: bool = False):
    candidates = [
        "C:/Windows/Fonts/segoeuib.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf",
        "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
        "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf",
    ]
    for candidate in candidates:
        try:
            return ImageFont.truetype(candidate, size)
        except Exception:
            continue
    return ImageFont.load_default()


def rounded_rect(draw: ImageDraw.ImageDraw, box, radius: int, fill, outline=None, width: int = 1):
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def center_text(draw: ImageDraw.ImageDraw, box, text: str, text_font, fill):
    bbox = draw.textbbox((0, 0), text, font=text_font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    x0, y0, x1, y1 = box
    x = x0 + (x1 - x0 - tw) / 2
    y = y0 + (y1 - y0 - th) / 2 - bbox[1]
    draw.text((x, y), text, font=text_font, fill=fill)


def create_base(size: int = 512) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    scale = size / 512

    def s(value: int) -> int:
        return int(value * scale)

    rounded_rect(draw, (s(34), s(34), s(478), s(478)), s(78), fill=(244, 242, 237, 255), outline=(122, 70, 52, 255), width=s(12))
    rounded_rect(draw, (s(70), s(70), s(442), s(442)), s(54), fill=(238, 233, 225, 255), outline=(139, 111, 91, 255), width=s(5))

    # Rail/decal stripe motif.
    draw.rectangle((s(92), s(338), s(420), s(372)), fill=(122, 70, 52, 255))
    draw.rectangle((s(92), s(392), s(420), s(426)), fill=(122, 70, 52, 255))
    for x in range(116, 410, 54):
        draw.polygon([(s(x), s(334)), (s(x + 28), s(334)), (s(x + 6), s(430)), (s(x - 22), s(430))], fill=(207, 227, 214, 255), outline=(139, 111, 91, 255))

    center_text(draw, (s(82), s(82), s(430), s(282)), "RM", font(s(176), bold=True), (46, 46, 46, 255))
    center_text(draw, (s(132), s(268), s(380), s(328)), "REPMARK", font(s(42), bold=True), (122, 70, 52, 255))
    center_text(draw, (s(172), s(436), s(340), s(468)), "RSS", font(s(30), bold=True), (122, 70, 52, 255))
    return img


def main() -> int:
    ASSETS.mkdir(parents=True, exist_ok=True)
    base = create_base()
    base.save(PNG_PATH)
    base.save(ICO_PATH, sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    print(f"Wrote {PNG_PATH}")
    print(f"Wrote {ICO_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
