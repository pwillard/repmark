# repmark

Generate transparent PNG decal sheets for railroad reporting marks from a YAML configuration file.

The script renders two groups of marks:

- `side_lines`: large side reporting marks, drawn one per row.
- `end_lines`: smaller end reporting marks, drawn stacked or inline.

It also writes bounding box files that can be used when placing decals in Blender/Open Rails workflows.

## Requirements

- Python 3
- Pillow
- PyYAML

## Usage

Generate a decal sheet from `config.yaml`:

```bash
python repmark.py --yaml config.yaml
```

The Windows command-line EXE accepts the same options:

```bat
dist/repmark.exe --yaml config.yaml
```

Draw red debug boxes around each text element:

```bash
python repmark.py --yaml config.yaml --draw-bboxes
```

Print bounding boxes to the console:

```bash
python repmark.py --yaml config.yaml --log-bboxes
```

Open the generated image after saving:

```bash
python repmark.py --yaml config.yaml --preview
```

Use a YAML file as the layout template and load reporting mark numbers from a CSV roster:

```bash
python repmark.py --yaml config.yaml --csv sample_roster.csv --prefix NS
```

Options can be combined:

```bash
python repmark.py --yaml config.yaml --draw-bboxes --preview
```

If `--yaml` is omitted, repmark uses its internal defaults.

If the file passed to `--yaml` does not exist, repmark creates a default config file at that path and renders from those defaults.

## GUI

RepMark Studio is a Tkinter front-end for the same `repmark.exe` command-line tool:

```bash
python repmark_gui.py
```

The GUI provides:

- YAML config browsing and recent-config history.
- Optional CSV roster browsing with reporting mark prefix entry.
- One-click decal generation.
- Toggles for red debug boxes, bbox logging, preview after generation, and opening the output folder.
- A dark output log showing the exact command, validation errors, layout warnings, and generated file paths.
- Light/Dark themes matching the Open Rails Shape Packer style.
- Custom RepMark/RailSimStuff icon and banner assets.
- A Program Settings field for the standalone `repmark.exe` backend.

To build a Windows GUI executable, install PyInstaller and run:

```bat
build_windows_gui.bat
```

The build script creates `dist\RepMarkStudio.exe`.

## Windows command-line EXE

To build a standalone command-line executable similar to ORZIP.EXE, run:

```bat
build_windows_cli.bat
```

The build script creates `dist/repmark.exe`. It supports the same options as the Python script:

```bat
dist/repmark.exe --yaml config.yaml --draw-bboxes --log-bboxes
```

## Output files

The main image path comes from the `out` setting in the YAML file. The sample config writes to `out/decal_custom.png`, so generated files land in an `out/` folder under the folder where the EXE or script is running.

For example, if `out` is `decal_custom.png`, repmark writes:

| File                         | Description                                                          |
| ---------------------------- | -------------------------------------------------------------------- |
| `decal_custom.png`           | Rendered transparent decal sheet.                                    |
| `decal_custom_bboxes.txt`    | Human-readable pixel coordinates for all rendered text.              |
| `decal_custom_bboxes.json`   | Machine-readable coordinates for Blender/Open Rails scripting.       |

## Configuration reference

| Key                 | Type               | Description |
| ------------------- | ------------------ | ----------- |
| `width`             | integer            | Output image width in pixels. |
| `height`            | integer            | Output image height in pixels. |
| `bgrgba`            | string             | Background RGBA as `"R,G,B,A"`. Use `"0,0,0,0"` for transparent. |
| `font_path`         | string             | Font file path. Relative paths can resolve from the config folder, app folder, or `fonts/`. |
| `out`               | string             | Output PNG path. |
| `font_color`        | list of 4 integers | Text color as `[R, G, B, A]`. |
| `draw_bboxes`       | boolean            | Draw red debug boxes without needing `--draw-bboxes`. |
| `bbox_padding`      | integer, optional  | Extra pixels around debug boxes. If omitted, padding scales with font size. |
| `side_font`         | integer            | Font size for `side_lines`. |
| `side_x`            | integer            | Left position for side marks. |
| `side_y`            | integer            | Top position for the first side mark. |
| `side_spacing`      | integer            | Vertical space between side marks. |
| `end_font`          | integer            | Font size for `end_lines`. |
| `end_x`             | integer            | Left position for end marks. |
| `end_y`             | integer            | Top position for the first end mark. |
| `end_spacing`       | integer            | Vertical space between end mark blocks. |
| `end_inner_gap`     | integer            | Vertical gap between stacked end mark parts. |
| `align_end_bottom_to_side` | boolean     | Shift end marks so the first end-mark bottom bbox aligns with the first side-mark bottom bbox. |
| `end_inline`        | boolean            | If true, end marks default to inline layout. If false, they default to stacked layout. |
| `inline_gap_factor` | number             | Gap between inline end mark parts, as a fraction of prefix width. |
| `csv_path`          | string, optional   | CSV roster path. When set, CSV rows replace `side_lines` and `end_lines` at run time. |
| `csv_prefix`        | string             | Reporting mark prefix used for one-column CSV files, such as `NS`. |
| `side_lines`        | list of strings    | Side marks to render. |
| `end_lines`         | list               | End marks to render. Entries may be strings or mappings with `value` and `stacked`. |

## CSV roster import

CSV import lets `config.yaml` act as the layout template while the roster supplies the reporting marks.

Simple one-column CSV files use the configured `csv_prefix` or the `--prefix` command-line option:

```csv
number
998235
998375
998369
```

Run it with:

```bash
python repmark.py --yaml config.yaml --csv sample_roster.csv --prefix NS
```

repmark converts those rows to:

- side text: `998 235`
- end text: `NS 998235`

CSV files may also include the prefix per row:

```csv
prefix,number
NS,998235
NS,998375
```

## End line formats

Stacked end mark:

```yaml
- value: "NS 998235"
  stacked: true
```

Inline end mark:

```yaml
- value: "NS 998235"
  stacked: false
```

String-only entries are also accepted. They use the global `end_inline` setting:

```yaml
- "NS 998235"
```

## Validation and layout warnings

repmark validates the YAML before rendering. Invalid values are reported as grouped errors instead of Python tracebacks.

After rendering, repmark checks every text bounding box. If text falls outside the image canvas, it prints a warning showing which entry overflowed and by how many pixels.

