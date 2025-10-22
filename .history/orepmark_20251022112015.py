#!/usr/bin/env python3
#-------------------------------------------------------------------------------
# Name:        REPMARK.PY 
# Purpose:     Generate NS MOW Gondola Reporting Marks (YAML configurable)
#              For Blender/OpenRails decal sheets with alpha
# Author:      Pete Willard (refactor by ChatGPT)
# Created:     2023-08-29  |  Updated: 2025-10-21
# License:     CC BY-SA 4.0
#-------------------------------------------------------------------------------

from PIL import Image, ImageDraw, ImageFont
import argparse
import csv
import yaml
import json
from pathlib import Path
from typing import List, Tuple, Union

# === Defaults ===
DEFAULT_SIDE_LINES = [
    "999 286","998 375","998 369","998 366","998 344",
    "998 343","998 355","998 349","998 293","998 292",
    "998 279","998 270","998 235"
]

DEFAULT_END_LINES = [
    {"value": "NS 999286", "stacked": True},
    {"value": "NS 998375", "stacked": True},
    {"value": "NS 998369", "stacked": True},
    {"value": "NS 998366", "stacked": True},
    {"value": "NS 998344", "stacked": True},
    {"value": "NS 998343", "stacked": True},
    {"value": "NS 998355", "stacked": True},
    {"value": "NS 998349", "stacked": True},
    {"value": "NS 998293", "stacked": True},
    {"value": "NS 998292", "stacked": True},
    {"value": "NS 998279", "stacked": True},
    {"value": "NS 998270", "stacked": True},
    {"value": "NS 998235", "stacked": True}
]

DEFAULT_CONFIG = {
    "width": 1024,
    "height": 1024,
    "bgrgba": "0,0,0,0",
    "side_font": 64,
    "end_font": 28,
    "side_x": 5,
    "side_y": 5,
    "side_spacing": 10,
    "end_x": 500,
    "end_y": 5,
    "end_spacing": 20,
    "end_inner_gap": 0,
    "end_inline": False,
    "font_path": "helvetica-b.ttf",
    "out": "decalresult.png",
    "font_color": [189, 204, 223, 255],
    "side_lines": DEFAULT_SIDE_LINES,
    "end_lines": DEFAULT_END_LINES,
    "inline_gap_factor": 0.3,
    "draw_bboxes": False
}

padding = 5  # pixels of buffer space around text

# === Font loader ===
def load_font(font_path: Path, size: int) -> ImageFont.FreeTypeFont:
    try:
        return ImageFont.truetype(str(font_path), size)
    except Exception:
        try:
            return ImageFont.truetype("DejaVuSans.ttf", size)
        except Exception:
            return ImageFont.load_default()

# === CSV reader ===
def read_lines_csv(csv_path: Path) -> List[str]:
    lines = []
    with csv_path.open(newline='', encoding='utf-8-sig') as f:
        reader = csv.reader(f)
        for row in reader:
            if not row:
                continue
            val = row[0].strip()
            if val:
                lines.append(val)
    return lines

# === YAML loader ===
def load_yaml_config(yaml_path: Path) -> dict:
    """Load YAML config; create default if missing."""
    if not yaml_path.exists():
        print(f"⚙️ Config file '{yaml_path}' not found. Creating default...")
        with yaml_path.open("w", encoding="utf-8") as f:
            yaml.safe_dump(DEFAULT_CONFIG, f, sort_keys=False)
        print(f"✅ Default config created at '{yaml_path}'. Edit it to customize.")
        return DEFAULT_CONFIG
    with yaml_path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    merged = {**DEFAULT_CONFIG, **data}
    return merged

# === Drawing functions ===
def draw_block_inline(draw, lines, font, start_xy, line_spacing, fill_rgba):
    x, y = start_xy
    results = []
    for line in lines:
        draw.text((x, y), line, font=font, fill=fill_rgba)
        bbox = draw.textbbox((x, y), line, font=font)
        results.append((line, bbox))
        y += font.size + line_spacing
    return results

def draw_block_stacked_on_space(
    draw,
    lines: List[Union[str, dict]],
    font,
    start_xy,
    block_spacing,
    inner_stack_gap=0,
    fill_rgba=(189,204,223,255),
    force_stack_default=False,
    inline_gap_factor: float = 0.3
):
    """
    Draw text blocks that can be stacked or inline with adaptive spacing.
    Behavior:
      - If entry is dict: {'value': 'NS 998286', 'stacked': True/False}
      - If stacked=True -> vertical stack
      - If stacked=False but has space -> inline with adaptive gap
      - If no 'stacked' flag, fall back to global force_stack_default
    """
    x, y = start_xy
    results = []

    for entry in lines:
        if isinstance(entry, dict):
            line = entry.get("value", "")
            stacked_flag = entry.get("stacked", None)
        else:
            line = str(entry)
            stacked_flag = None

        if " " in line:
            top, bottom = line.split(" ", 1)
        else:
            top, bottom = line, ""

        has_space = bool(bottom)
        if stacked_flag is None:
            do_stack = force_stack_default and has_space
        else:
            do_stack = bool(stacked_flag) and has_space

        if do_stack:
            # --- Vertical stacking ---
            draw.text((x, y), top, font=font, fill=fill_rgba)
            bbox_top = draw.textbbox((x, y), top, font=font)
            y2 = y + font.size + inner_stack_gap
            draw.text((x, y2), bottom, font=font, fill=fill_rgba)
            bbox_bottom = draw.textbbox((x, y2), bottom, font=font)
            y += (font.size * 2) + inner_stack_gap + block_spacing
        elif has_space:
            # --- Inline with adaptive gap ---
            prefix_width = draw.textlength(top, font=font)
            adaptive_gap = int(prefix_width * inline_gap_factor)
            draw.text((x, y), top, font=font, fill=fill_rgba)
            x2 = x + prefix_width + adaptive_gap
            draw.text((x2, y), bottom, font=font, fill=fill_rgba)
            bbox_top = draw.textbbox((x, y), top, font=font)
            bbox_bottom = draw.textbbox((x2, y), bottom, font=font)
            combined_bbox = (bbox_top[0], bbox_top[1], bbox_bottom[2], bbox_bottom[3])
            y += font.size + block_spacing
            results.append((line, bbox_top, combined_bbox))
            continue
        else:
            # --- Single unstacked line ---
            draw.text((x, y), line, font=font, fill=fill_rgba)
            bbox_top = draw.textbbox((x, y), line, font=font)
            bbox_bottom = bbox_top
            y += font.size + block_spacing

        results.append((line, bbox_top, bbox_bottom))
    return results

# === Export + Draw BBoxes ===
"""Export bounding box data and optionally draw outlines."""
def export_and_draw_bounding_boxes(
    draw,
    image,
    side_results,
    end_results,
    out_path_base="bbox_data",
    draw_boxes=False,
    side_font_size=64,
    end_font_size=28,
    bbox_padding=None  # None means auto-scale mode
):
        
    txt_path = Path(f"{out_path_base}_bboxes.txt")
    json_path = Path(f"{out_path_base}_bboxes.json")

    # --- Text log ---
    with txt_path.open("w", encoding="utf-8") as f:
        f.write("=== SIDE LINES BOUNDARIES ===\n")
        for line, bbox in side_results:
            f.write(f"[SIDE] {line:>10s}  bbox={bbox}\n")
        f.write("\n=== END LINES BOUNDARIES ===\n")
        for line, bbox_top, bbox_bottom in end_results:
            if bbox_top == bbox_bottom:
                f.write(f"[END ] {line:>10s}  bbox={bbox_top}\n")
            else:
                f.write(f"[END ] {line:>10s}  top={bbox_top}  bottom={bbox_bottom}\n")

    # --- JSON data ---
    data = {
        "side": [{"text": line, "bbox": bbox} for line, bbox in side_results],
        "end": [
            {"text": line, "bbox_top": bbox_top, "bbox_bottom": bbox_bottom}
            for line, bbox_top, bbox_bottom in end_results
        ],
    }
    with json_path.open("w", encoding="utf-8") as jf:
        json.dump(data, jf, indent=2)
    print(f"🧾 Bounding box data saved → {txt_path} & {json_path}")


        # --- Draw outlines only if explicitly enabled ---
    if draw_boxes:
        # If no manual bbox_padding provided, scale padding to font size
        if bbox_padding is None:
            side_padding = max(2, int(side_font_size * 0.1))  # 10% of side font
            end_padding = max(2, int(end_font_size * 0.1))    # 10% of end font
            print(f"📐 Auto-padding: {side_padding}px (side), {end_padding}px (end)")
        else:
            side_padding = end_padding = bbox_padding
            print(f"📐 Manual padding: {bbox_padding}px")

        def pad_bbox(b, pad):
            x0, y0, x1, y1 = b
            return (x0 - pad, y0 - pad, x1 + pad, y1 + pad)

        # Draw side line outlines
        for _, bbox in side_results:
            draw.rectangle(pad_bbox(bbox, side_padding), outline=(255, 0, 0, 255), width=2)

        # Draw end line outlines
        for _, bbox_top, bbox_bottom in end_results:
            draw.rectangle(pad_bbox(bbox_top, end_padding), outline=(255, 0, 0, 255), width=2)
            if bbox_bottom != bbox_top:
                draw.rectangle(pad_bbox(bbox_bottom, end_padding), outline=(255, 0, 0, 255), width=2)

        print(f"🎨 Red outlines drawn on image.")
    else:
        print("🎨 Red outlines skipped (draw_bboxes=False).")


"""     # --- Draw outlines only if explicitly enabled ---
    if draw_boxes:
        padding = bbox_padding if "bbox_padding" in locals() else 10

        def pad_bbox(b):
            x0, y0, x1, y1 = b
            return (x0 - padding, y0 - padding, x1 + padding, y1 + padding)

        for _, bbox in side_results:
            draw.rectangle(pad_bbox(bbox), outline=(255, 0, 0, 255), width=2)

        for _, bbox_top, bbox_bottom in end_results:
            draw.rectangle(pad_bbox(bbox_top), outline=(255, 0, 0, 255), width=2)
            if bbox_bottom != bbox_top:
                draw.rectangle(pad_bbox(bbox_bottom), outline=(255, 0, 0, 255), width=2)

        print(f"🎨 Red outlines drawn on image (with {padding}px padding).")
    else:
        print("🎨 Red outlines skipped (draw_bboxes=False).")
 """

# === Main ===
def main():
    ap = argparse.ArgumentParser(description="Generate NS MOW gondola reporting mark decals with alpha.")
    ap.add_argument("--yaml", type=str, help="YAML config with rendering settings and line data")
    ap.add_argument("--draw-bboxes", action="store_true", help="Draw red bounding boxes for debugging")
    ap.add_argument("--log-bboxes", action="store_true", help="Print bounding boxes to console")
    args = ap.parse_args()

    cfg = load_yaml_config(Path(args.yaml)) if args.yaml else DEFAULT_CONFIG
    #draw_bboxes = args.draw_bboxes or cfg.get("draw_bboxes", False)

    # Draw red outlines only if explicitly enabled by CLI or YAML
    # Determine if red outlines should be drawn
    cfg_draw_bboxes = cfg.get("draw_bboxes", False)

    # Normalize possible YAML string values like "False" or "false"
    if isinstance(cfg_draw_bboxes, str):
        cfg_draw_bboxes = cfg_draw_bboxes.strip().lower() in ("1", "true", "yes", "on")

   

    # Only draw boxes if CLI explicitly requests it or YAML is true
    draw_bboxes = bool(args.draw_bboxes) or bool(cfg_draw_bboxes)
    # debug
    #print(f"🔧 draw_bboxes resolved to: {draw_bboxes}")

    w, h = cfg["width"], cfg["height"]
    bg = tuple(int(c) for c in cfg["bgrgba"].split(","))
    out_path = Path(cfg["out"])
    font_path = Path(cfg["font_path"])
    font_color = tuple(cfg["font_color"])
    side_lines = cfg["side_lines"]
    end_lines = cfg["end_lines"]

    # --- Canvas ---
    image = Image.new("RGBA", (w, h), bg)
    draw = ImageDraw.Draw(image)

    side_font = load_font(font_path, cfg["side_font"])
    end_font  = load_font(font_path, cfg["end_font"])

    # --- Draw sides ---
    side_results = draw_block_inline(draw, side_lines, side_font, (cfg["side_x"], cfg["side_y"]), cfg["side_spacing"], font_color)

    # --- Draw ends ---
    end_results = draw_block_stacked_on_space(
        draw,
        end_lines,
        end_font,
        (cfg["end_x"], cfg["end_y"]),
        cfg["end_spacing"],
        cfg["end_inner_gap"],
        font_color,
        force_stack_default=not cfg["end_inline"],
        inline_gap_factor=cfg.get("inline_gap_factor", 0.3)
    )

    # --- Save image and export data ---
    export_and_draw_bounding_boxes(
        draw,
        image,
        side_results,
        end_results,
        out_path_base=out_path.stem,
        draw_boxes=draw_bboxes,
        side_font_size=cfg["side_font"],
        end_font_size=cfg["end_font"],
        bbox_padding=cfg.get("bbox_padding", None)
    )


    # Save after drawing outlines (so they’re visible)
    image.save(out_path)
    image.close()

    if args.log_bboxes:
        for line, bbox in side_results:
            print(f"[SIDE] {line:>10s}  bbox={bbox}")
        for line, bbox_top, bbox_bottom in end_results:
            if bbox_top == bbox_bottom:
                print(f"[END ] {line:>10s}  bbox={bbox_top}")
            else:
                print(f"[END ] {line:>10s}  top={bbox_top}  bottom={bbox_bottom}")

    print(f"✅ Done. Output saved to {out_path}")

if __name__ == "__main__":
    main()
