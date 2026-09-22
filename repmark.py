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
import os
import subprocess
import sys
import yaml
import json
from pathlib import Path
from typing import List, Tuple, Union

VERSION_FALLBACK = "1.0.7"


def load_app_version() -> str:
    """Load the visible app version from VERSION, with a safe frozen fallback."""
    bases = [Path(__file__).resolve().parent]
    if getattr(sys, "frozen", False):
        bases.insert(0, Path(sys.executable).resolve().parent)
    if hasattr(sys, "_MEIPASS"):
        bases.insert(0, Path(sys._MEIPASS))  # type: ignore[attr-defined]
    for base in bases:
        version_file = base / "VERSION"
        if version_file.exists():
            value = version_file.read_text(encoding="utf-8").strip()
            if value:
                return value
    return VERSION_FALLBACK


APP_VERSION = load_app_version()

def configure_stdio():
    """Avoid Windows console encoding crashes when status messages contain symbols."""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="replace")

# === Defaults ===
DEFAULT_SIDE_LINES = [
    "998 286","998 375","998 369","998 366","998 344",
    "998 343","998 355","998 349","998 293","998 292",
    "998 279","998 270","998 235"
]

DEFAULT_END_LINES = [
    {"value": "NS 998286", "stacked": True},
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
    "end_font": 27,
    "side_x": 5,
    "side_y": 5,
    "side_spacing": 10,
    "end_x": 500,
    "end_y": 5,
    "end_spacing": 20,
    "end_inner_gap": 0,
    "align_end_bottom_to_side": True,
    "end_inline": False,
    "font_path": "fonts/helvetica-b.ttf",
    "out": "out/decalresult.png",
    "font_color": [189, 204, 223, 255],
    "font_stroke_width": 0,
    "side_lines": DEFAULT_SIDE_LINES,
    "end_lines": DEFAULT_END_LINES,
    "inline_gap_factor": 0.3,
    "draw_bboxes": False,
    "csv_path": "",
    "csv_prefix": "NS"
}

def app_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent

def bundled_dir() -> Path:
    return Path(getattr(sys, "_MEIPASS", app_dir())).resolve()

def resolve_font_path(font_path: Path, config_dir: Path | None = None) -> Path:
    """Resolve fonts from the config folder, app folder, bundled files, or fonts/."""
    if font_path.is_absolute() and font_path.exists():
        return font_path

    candidates = []
    if config_dir is not None:
        candidates.append(config_dir / font_path)
    for base in (app_dir(), bundled_dir()):
        candidates.extend([
            base / font_path,
            base / "fonts" / font_path.name,
        ])
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return font_path

# === Font loader ===
def load_font(font_path: Path, size: int, config_dir: Path | None = None) -> ImageFont.FreeTypeFont:
    resolved_font = resolve_font_path(font_path, config_dir)
    try:
        return ImageFont.truetype(str(resolved_font), size)
    except Exception:
        try:
            return ImageFont.truetype("DejaVuSans.ttf", size)
        except Exception:
            return ImageFont.load_default()

def normalize_roster_number(value: str) -> str:
    """Normalize a roster number while preserving user-supplied digits/letters."""
    return "".join(ch for ch in value.strip() if ch.isalnum())

def format_side_number(number: str) -> str:
    """Format compact car numbers for large side marks, e.g. 998235 -> 998 235."""
    stripped = number.strip()
    if " " in stripped:
        return stripped
    compact = normalize_roster_number(stripped)
    if len(compact) > 3:
        return f"{compact[:-3]} {compact[-3:]}"
    return compact

def read_roster_csv(csv_path: Path, default_prefix: str) -> List[Tuple[str, str]]:
    """Read reporting mark prefix and number rows from a CSV roster."""
    rows = []
    with csv_path.open(newline='', encoding='utf-8-sig') as f:
        reader = csv.reader(f)
        for row in reader:
            cleaned = [cell.strip() for cell in row]
            if not cleaned or not any(cleaned) or cleaned[0].startswith("#"):
                continue
            rows.append(cleaned)

    if not rows:
        raise ValueError(f"CSV roster '{csv_path}' does not contain any reporting mark rows.")

    header_names = {"prefix", "reporting_mark", "road", "railroad", "mark", "number", "car_number", "road_number"}
    first_row = [cell.strip().lower() for cell in rows[0]]
    has_header = any(cell in header_names for cell in first_row)
    data_rows = rows[1:] if has_header else rows

    prefix_index = None
    number_index = 0
    if has_header:
        for candidate in ("number", "car_number", "road_number"):
            if candidate in first_row:
                number_index = first_row.index(candidate)
                break
        for candidate in ("prefix", "reporting_mark", "road", "railroad", "mark"):
            if candidate in first_row:
                prefix_index = first_row.index(candidate)
                break
    elif len(rows[0]) >= 2 and not rows[0][0].strip().isdigit() and rows[0][1].strip():
        prefix_index = 0
        number_index = 1

    marks = []
    for row_number, row in enumerate(data_rows, start=(2 if has_header else 1)):
        if number_index >= len(row):
            raise ValueError(f"CSV roster '{csv_path}' row {row_number} is missing a car number.")
        number = normalize_roster_number(row[number_index])
        if not number:
            continue
        prefix = default_prefix.strip()
        if prefix_index is not None and prefix_index < len(row) and row[prefix_index].strip():
            prefix = row[prefix_index].strip().upper()
        if not prefix:
            raise ValueError(f"CSV roster '{csv_path}' row {row_number} does not have a reporting mark prefix.")
        marks.append((prefix, number))

    if not marks:
        raise ValueError(f"CSV roster '{csv_path}' does not contain any usable reporting mark rows.")
    return marks

def reporting_marks_to_lines(marks: List[Tuple[str, str]]) -> Tuple[List[str], List[dict]]:
    """Convert roster entries into side_lines and end_lines config values."""
    side_lines = [format_side_number(number) for _, number in marks]
    end_lines = [{"value": f"{prefix} {number}", "stacked": True} for prefix, number in marks]
    return side_lines, end_lines

def apply_csv_roster(cfg: dict) -> dict:
    """Replace template line lists with rows read from csv_path, when configured."""
    csv_path_value = str(cfg.get("csv_path", "") or "").strip()
    if not csv_path_value:
        return cfg
    base_dir = Path(cfg.get("_config_dir", Path.cwd()))
    csv_path = Path(csv_path_value)
    if not csv_path.is_absolute():
        csv_path = base_dir / csv_path
    if not csv_path.exists():
        raise ValueError(f"CSV roster file not found: {csv_path}")
    prefix = str(cfg.get("csv_prefix", "NS") or "").strip().upper()
    marks = read_roster_csv(csv_path, prefix)
    side_lines, end_lines = reporting_marks_to_lines(marks)
    cfg = {**cfg, "side_lines": side_lines, "end_lines": end_lines}
    print(f"📄 Loaded {len(marks)} reporting mark(s) from {csv_path}")
    return cfg

# === YAML loader ===
def load_yaml_config(yaml_path: Path) -> dict:
    """Load YAML config; create default if missing."""
    if not yaml_path.exists():
        print(f"⚙️ Config file '{yaml_path}' not found. Creating default...")
        with yaml_path.open("w", encoding="utf-8") as f:
            yaml.safe_dump(DEFAULT_CONFIG, f, sort_keys=False)
        print(f"✅ Default config created at '{yaml_path}'. Edit it to customize.")
        return DEFAULT_CONFIG
    try:
        with yaml_path.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    except yaml.YAMLError as exc:
        raise ValueError(f"Could not parse YAML config '{yaml_path}': {exc}") from exc

    if not isinstance(data, dict):
        raise ValueError(f"YAML config '{yaml_path}' must contain key/value settings at the top level.")

    merged = {**DEFAULT_CONFIG, **data}
    merged["_config_dir"] = str(yaml_path.resolve().parent)
    return merged

def parse_rgba_string(value, field_name):
    """Parse a comma-separated RGBA string into a tuple of four integers."""
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a comma-separated RGBA string like '0,0,0,0'.")

    parts = [part.strip() for part in value.split(",")]
    if len(parts) != 4:
        raise ValueError(f"{field_name} must contain exactly four comma-separated values.")

    try:
        rgba = tuple(int(part) for part in parts)
    except ValueError as exc:
        raise ValueError(f"{field_name} must contain only integer values.") from exc

    validate_rgba(rgba, field_name)
    return rgba

def validate_rgba(value, field_name):
    """Validate an RGBA tuple/list."""
    if not isinstance(value, (list, tuple)) or len(value) != 4:
        raise ValueError(f"{field_name} must be four integers: [R, G, B, A].")
    if not all(isinstance(channel, int) for channel in value):
        raise ValueError(f"{field_name} must contain only integers.")
    if not all(0 <= channel <= 255 for channel in value):
        raise ValueError(f"{field_name} values must be between 0 and 255.")

def validate_config(cfg):
    """Validate user-facing config values before rendering."""
    errors = []

    def require_int(field_name, minimum=None):
        value = cfg.get(field_name)
        if not isinstance(value, int):
            errors.append(f"{field_name} must be an integer.")
            return
        if minimum is not None and value < minimum:
            errors.append(f"{field_name} must be at least {minimum}.")

    for field_name in ("width", "height", "side_font", "end_font"):
        require_int(field_name, 1)

    for field_name in ("side_x", "side_y", "side_spacing", "end_x", "end_y", "end_spacing", "end_inner_gap"):
        require_int(field_name)

    if not isinstance(cfg.get("out"), str) or not cfg.get("out", "").strip():
        errors.append("out must be a non-empty output PNG path.")

    if not isinstance(cfg.get("font_path"), str) or not cfg.get("font_path", "").strip():
        errors.append("font_path must be a non-empty font path.")

    try:
        parse_rgba_string(cfg.get("bgrgba"), "bgrgba")
    except ValueError as exc:
        errors.append(str(exc))

    try:
        validate_rgba(cfg.get("font_color"), "font_color")
    except ValueError as exc:
        errors.append(str(exc))

    if "font_stroke_width" in cfg:
        if not isinstance(cfg["font_stroke_width"], int) or cfg["font_stroke_width"] < 0:
            errors.append("font_stroke_width must be a non-negative integer.")

    if not isinstance(cfg.get("side_lines"), list):
        errors.append("side_lines must be a list of text strings.")
    else:
        for index, line in enumerate(cfg["side_lines"], start=1):
            if not isinstance(line, str):
                errors.append(f"side_lines entry {index} must be a text string.")

    if not isinstance(cfg.get("end_lines"), list):
        errors.append("end_lines must be a list of text strings or {value, stacked} entries.")
    else:
        for index, entry in enumerate(cfg["end_lines"], start=1):
            if isinstance(entry, str):
                continue
            if not isinstance(entry, dict):
                errors.append(f"end_lines entry {index} must be a text string or mapping.")
                continue
            if not isinstance(entry.get("value"), str) or not entry.get("value", "").strip():
                errors.append(f"end_lines entry {index} must include a non-empty text value.")
            if "stacked" in entry and not isinstance(entry["stacked"], bool):
                errors.append(f"end_lines entry {index} stacked must be true or false.")

    if "inline_gap_factor" in cfg and not isinstance(cfg["inline_gap_factor"], (int, float)):
        errors.append("inline_gap_factor must be a number.")

    if "bbox_padding" in cfg and cfg["bbox_padding"] is not None:
        if not isinstance(cfg["bbox_padding"], int) or cfg["bbox_padding"] < 0:
            errors.append("bbox_padding must be a non-negative integer.")

    if "align_end_bottom_to_side" in cfg and not isinstance(cfg["align_end_bottom_to_side"], bool):
        errors.append("align_end_bottom_to_side must be true or false.")

    if "csv_path" in cfg and cfg["csv_path"] not in (None, "") and not isinstance(cfg["csv_path"], str):
        errors.append("csv_path must be a CSV file path string.")

    if "csv_prefix" in cfg and (not isinstance(cfg["csv_prefix"], str) or not cfg["csv_prefix"].strip()):
        errors.append("csv_prefix must be a non-empty reporting mark prefix, such as NS.")

    if errors:
        print("❌ Config validation failed:")
        for error in errors:
            print(f"   - {error}")
        return False

    return True

# === Drawing functions ===
def draw_text(draw, xy, text, font, fill_rgba, stroke_width=0):
    draw.text(
        xy,
        text,
        font=font,
        fill=fill_rgba,
        stroke_width=stroke_width,
        stroke_fill=fill_rgba,
    )


def text_bbox(draw, xy, text, font, stroke_width=0):
    return draw.textbbox(xy, text, font=font, stroke_width=stroke_width)


def draw_block_inline(draw, lines, font, start_xy, line_spacing, fill_rgba, stroke_width=0):
    x, y = start_xy
    results = []
    for line in lines:
        draw_text(draw, (x, y), line, font, fill_rgba, stroke_width)
        bbox = text_bbox(draw, (x, y), line, font, stroke_width)
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
    inline_gap_factor: float = 0.3,
    stroke_width: int = 0,
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
            draw_text(draw, (x, y), top, font, fill_rgba, stroke_width)
            bbox_top = text_bbox(draw, (x, y), top, font, stroke_width)
            y2 = y + font.size + inner_stack_gap
            draw_text(draw, (x, y2), bottom, font, fill_rgba, stroke_width)
            bbox_bottom = text_bbox(draw, (x, y2), bottom, font, stroke_width)
            y += (font.size * 2) + inner_stack_gap + block_spacing
        elif has_space:
            # --- Inline with adaptive gap ---
            prefix_width = draw.textlength(top, font=font)
            adaptive_gap = int(prefix_width * inline_gap_factor)
            draw_text(draw, (x, y), top, font, fill_rgba, stroke_width)
            x2 = x + prefix_width + adaptive_gap
            draw_text(draw, (x2, y), bottom, font, fill_rgba, stroke_width)
            bbox_top = text_bbox(draw, (x, y), top, font, stroke_width)
            bbox_bottom = text_bbox(draw, (x2, y), bottom, font, stroke_width)
            combined_bbox = (bbox_top[0], bbox_top[1], bbox_bottom[2], bbox_bottom[3])
            y += font.size + block_spacing
            results.append((line, bbox_top, combined_bbox))
            continue
        else:
            # --- Single unstacked line ---
            draw_text(draw, (x, y), line, font, fill_rgba, stroke_width)
            bbox_top = text_bbox(draw, (x, y), line, font, stroke_width)
            bbox_bottom = bbox_top
            y += font.size + block_spacing

        results.append((line, bbox_top, bbox_bottom))
    return results

def describe_bbox_overflow(bbox, width, height):
    """Return readable canvas overflow messages for a PIL bbox."""
    x0, y0, x1, y1 = bbox
    overflow = []
    if x0 < 0:
        overflow.append(f"left by {-x0}px")
    if y0 < 0:
        overflow.append(f"top by {-y0}px")
    if x1 > width:
        overflow.append(f"right by {x1 - width}px")
    if y1 > height:
        overflow.append(f"bottom by {y1 - height}px")
    return overflow

def warn_if_text_exceeds_canvas(side_results, end_results, width, height):
    """Warn when rendered text falls outside the image canvas."""
    warnings = []

    for line, bbox in side_results:
        overflow = describe_bbox_overflow(bbox, width, height)
        if overflow:
            warnings.append(("SIDE", line, bbox, overflow))

    for line, bbox_top, bbox_bottom in end_results:
        overflow_top = describe_bbox_overflow(bbox_top, width, height)
        if overflow_top:
            warnings.append(("END top", line, bbox_top, overflow_top))

        if bbox_bottom != bbox_top:
            overflow_bottom = describe_bbox_overflow(bbox_bottom, width, height)
            if overflow_bottom:
                warnings.append(("END bottom", line, bbox_bottom, overflow_bottom))

    if not warnings:
        print("✅ Layout check: all text is within the canvas.")
        return 0

    print(f"⚠️ Layout warning: {len(warnings)} text box(es) exceed the {width}x{height} canvas:")
    for label, line, bbox, overflow in warnings:
        print(f"   [{label}] {line!r} bbox={bbox} exceeds canvas {', '.join(overflow)}")
    print("   Adjust canvas size, font size, x/y position, or spacing to keep text visible.")
    return len(warnings)

def aligned_end_y(cfg, side_results, end_lines, end_font, font_color, image_size):
    """Shift end text so its first bottom bbox matches the first side bbox bottom."""
    start_y = cfg["end_y"]
    if not cfg.get("align_end_bottom_to_side", False) or not side_results or not end_lines:
        return start_y

    trial_image = Image.new("RGBA", image_size, (0, 0, 0, 0))
    trial_draw = ImageDraw.Draw(trial_image)
    trial_results = draw_block_stacked_on_space(
        trial_draw,
        end_lines,
        end_font,
        (cfg["end_x"], start_y),
        cfg["end_spacing"],
        cfg["end_inner_gap"],
        font_color,
        force_stack_default=not cfg["end_inline"],
        inline_gap_factor=cfg.get("inline_gap_factor", 0.3),
        stroke_width=cfg.get("font_stroke_width", 0),
    )
    if not trial_results:
        return start_y

    first_side_bottom = side_results[0][1][3]
    first_end_bottom = trial_results[0][2][3]
    adjusted_y = start_y + (first_side_bottom - first_end_bottom)
    if adjusted_y != start_y:
        print(f"↕️ End text y adjusted from {start_y} to {adjusted_y} to align first-row bbox bottoms.")
    return adjusted_y

def open_preview(out_path: Path):
    """Open the generated image with the system's default image viewer."""
    resolved_path = out_path.resolve()

    try:
        if hasattr(os, "startfile"):
            os.startfile(resolved_path)  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(resolved_path)])
        else:
            subprocess.Popen(["xdg-open", str(resolved_path)])
    except Exception as exc:
        print(f"⚠️ Preview could not be opened automatically: {exc}")
        print(f"   Open manually: {resolved_path}")
        return False

    print(f"👁️ Preview opened: {resolved_path}")
    return True

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
    txt_path.parent.mkdir(parents=True, exist_ok=True)

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

        print("🎨 Red outlines drawn on image.")
    else:
        print("🎨 Red outlines skipped (draw_bboxes=False).")

# === Main ===
def main():
    configure_stdio()
    ap = argparse.ArgumentParser(description="Generate NS MOW gondola reporting mark decals with alpha.")
    ap.add_argument("--yaml", type=str, help="YAML config with rendering settings and line data")
    ap.add_argument("--draw-bboxes", action="store_true", help="Draw red bounding boxes for debugging")
    ap.add_argument("--log-bboxes", action="store_true", help="Print bounding boxes to console")
    ap.add_argument("--preview", action="store_true", help="Open the generated image after saving")
    ap.add_argument("--csv", type=str, help="CSV roster of car numbers to render with the YAML layout template")
    ap.add_argument("--prefix", type=str, help="Reporting mark prefix for one-column CSV rosters, e.g. NS")
    ap.add_argument("--version", action="version", version=f"repmark {APP_VERSION}")
    args = ap.parse_args()

    try:
        cfg = load_yaml_config(Path(args.yaml)) if args.yaml else DEFAULT_CONFIG
    except ValueError as exc:
        print(f"❌ {exc}")
        sys.exit(2)

    cfg_draw_bboxes = cfg.get("draw_bboxes", False)
    if isinstance(cfg_draw_bboxes, str):
        cfg_draw_bboxes = cfg_draw_bboxes.strip().lower() in ("1", "true", "yes", "on")

    draw_bboxes = bool(args.draw_bboxes) or bool(cfg_draw_bboxes)

    if args.csv:
        cfg["csv_path"] = args.csv
    if args.prefix:
        cfg["csv_prefix"] = args.prefix

    if not validate_config(cfg):
        sys.exit(2)

    try:
        cfg = apply_csv_roster(cfg)
    except ValueError as exc:
        print(f"❌ {exc}")
        sys.exit(2)

    w, h = cfg["width"], cfg["height"]
    bg = parse_rgba_string(cfg["bgrgba"], "bgrgba")
    out_path = Path(cfg["out"])
    config_dir = Path(cfg.get("_config_dir", app_dir()))
    font_path = Path(cfg["font_path"])
    font_color = tuple(cfg["font_color"])
    font_stroke_width = cfg.get("font_stroke_width", 0)
    side_lines = cfg["side_lines"]
    end_lines = cfg["end_lines"]

    # --- Canvas ---
    image = Image.new("RGBA", (w, h), bg)
    draw = ImageDraw.Draw(image)

    side_font = load_font(font_path, cfg["side_font"], config_dir)
    end_font  = load_font(font_path, cfg["end_font"], config_dir)

    # --- Draw sides ---
    side_results = draw_block_inline(draw, side_lines, side_font, (cfg["side_x"], cfg["side_y"]), cfg["side_spacing"], font_color, font_stroke_width)

    # --- Draw ends ---
    end_start_y = aligned_end_y(cfg, side_results, end_lines, end_font, font_color, (w, h))
    end_results = draw_block_stacked_on_space(
        draw,
        end_lines,
        end_font,
        (cfg["end_x"], end_start_y),
        cfg["end_spacing"],
        cfg["end_inner_gap"],
        font_color,
        force_stack_default=not cfg["end_inline"],
        inline_gap_factor=cfg.get("inline_gap_factor", 0.3),
        stroke_width=font_stroke_width,
    )

    warn_if_text_exceeds_canvas(side_results, end_results, w, h)

    # --- Save image and export data ---
    export_and_draw_bounding_boxes(
        draw,
        image,
        side_results,
        end_results,
        out_path_base=out_path.with_suffix(""),
        draw_boxes=draw_bboxes,
        side_font_size=cfg["side_font"],
        end_font_size=cfg["end_font"],
        bbox_padding=cfg.get("bbox_padding", None)
    )


    # Save after drawing outlines (so they’re visible)
    out_path.parent.mkdir(parents=True, exist_ok=True)
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

    if args.preview:
        open_preview(out_path)

if __name__ == "__main__":
    main()
