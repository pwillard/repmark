# repmark

Decal Sheet Creation based on YAML configuration

## Usage: 

Basic Usage:  `python repmark.py --yaml config.yaml`

Force Red Bounding Boxes: `python repmark.py --yaml config.yaml --draw-bboxes`

| File                      | Description                                                          |
| ------------------------- | -------------------------------------------------------------------- |
| `decalresult.png`         | Rendered decal (with or without red outlines).                       |
| `decalresult_bboxes.txt`  | Readable pixel coordinates for all text.                             |
| `decalresult_bboxes.json` | Machine-readable coordinates for use in Blender/OpenRails scripting. |

