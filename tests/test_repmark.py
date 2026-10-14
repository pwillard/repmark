"""Regression tests for repmark.py.

Run from the repo root:
    run_tests.bat
or:
    uv run --no-project --with pillow --with pyyaml python -m unittest discover -s tests -v
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import repmark  # noqa: E402

RED = (255, 0, 0, 255)


def write_config(folder: Path, name: str = "cfg.yaml", **overrides) -> Path:
    """Write a small, fast-rendering YAML config into folder."""
    cfg = {
        "width": 512,
        "height": 512,
        "side_font": 40,
        "end_font": 18,
        "end_x": 300,
        "font_path": "fonts/helvetica-b.ttf",
        "out": "out/test.png",
        "side_lines": ["998 235", "998 375"],
        "end_lines": [{"value": "NS 998235", "stacked": True}, {"value": "NS 998375", "stacked": True}],
    }
    cfg.update(overrides)
    path = folder / name
    import yaml
    path.write_text(yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8")
    return path


def run_cli(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(ROOT / "repmark.py"), *args],
        cwd=cwd,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=120,
    )


def count_color(path: Path, color) -> int:
    with Image.open(path) as im:
        rgba = im.convert("RGBA")
        colors = rgba.getcolors(maxcolors=rgba.width * rgba.height) or []
        return sum(count for count, value in colors if value == color)


class CliTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()


# --- 1. Missing fonts must fail loudly -------------------------------------
class FontErrorTests(CliTestCase):
    def test_missing_font_fails_without_output(self):
        cfg = write_config(self.tmp, font_path="fonts/does-not-exist.ttf")
        result = run_cli(self.tmp, "--yaml", str(cfg))
        self.assertEqual(result.returncode, 2, result.stdout)
        self.assertIn("does-not-exist.ttf", result.stdout)
        self.assertIn("Font", result.stdout)
        self.assertFalse((self.tmp / "out" / "test.png").exists())

    def test_unreadable_font_fails(self):
        bogus = self.tmp / "bogus.ttf"
        bogus.write_text("not a font", encoding="utf-8")
        cfg = write_config(self.tmp, font_path="bogus.ttf")
        result = run_cli(self.tmp, "--yaml", str(cfg))
        self.assertEqual(result.returncode, 2, result.stdout)
        self.assertIn("bogus.ttf", result.stdout)
        self.assertFalse((self.tmp / "out" / "test.png").exists())

    def test_load_font_raises_for_missing_font(self):
        with self.assertRaises(ValueError):
            repmark.load_font(Path("fonts/does-not-exist.ttf"), 20, self.tmp)

    def test_bundled_font_renders(self):
        cfg = write_config(self.tmp)
        result = run_cli(self.tmp, "--yaml", str(cfg))
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertTrue((self.tmp / "out" / "test.png").exists())


# --- 2. Debug boxes go to a separate image ---------------------------------
class DebugImageTests(CliTestCase):
    def test_draw_bboxes_keeps_main_png_clean(self):
        clean_cfg = write_config(self.tmp, "clean.yaml", out="clean/test.png")
        boxed_cfg = write_config(self.tmp, "boxed.yaml", out="boxed/test.png")
        self.assertEqual(run_cli(self.tmp, "--yaml", str(clean_cfg)).returncode, 0)
        result = run_cli(self.tmp, "--yaml", str(boxed_cfg), "--draw-bboxes")
        self.assertEqual(result.returncode, 0, result.stdout)

        clean_png = self.tmp / "clean" / "test.png"
        boxed_png = self.tmp / "boxed" / "test.png"
        debug_png = self.tmp / "boxed" / "test_debug.png"
        with Image.open(clean_png) as a, Image.open(boxed_png) as b:
            self.assertEqual(a.tobytes(), b.tobytes(), "main PNG must not contain debug boxes")
        self.assertEqual(count_color(boxed_png, RED), 0)
        self.assertTrue(debug_png.exists(), result.stdout)
        self.assertGreater(count_color(debug_png, RED), 0)
        self.assertFalse((self.tmp / "clean" / "test_debug.png").exists())

    def test_draw_bboxes_from_yaml_setting(self):
        cfg = write_config(self.tmp, draw_bboxes=True)
        result = run_cli(self.tmp, "--yaml", str(cfg))
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(count_color(self.tmp / "out" / "test.png", RED), 0)
        self.assertGreater(count_color(self.tmp / "out" / "test_debug.png", RED), 0)

    def test_gui_output_marker_points_at_clean_png(self):
        cfg = write_config(self.tmp)
        result = run_cli(self.tmp, "--yaml", str(cfg), "--draw-bboxes")
        marker_lines = [line for line in result.stdout.splitlines() if "Output saved to " in line]
        self.assertEqual(len(marker_lines), 1, result.stdout)
        self.assertTrue(marker_lines[0].rstrip().endswith("test.png"), marker_lines[0])


# --- 4. Side/end count mismatch warning ------------------------------------
class CountMismatchTests(CliTestCase):
    def test_mismatch_warns_but_succeeds(self):
        cfg = write_config(self.tmp, end_lines=[{"value": "NS 998235", "stacked": True}])
        result = run_cli(self.tmp, "--yaml", str(cfg))
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("2 side_lines but 1 end_lines", result.stdout)

    def test_matched_counts_do_not_warn(self):
        cfg = write_config(self.tmp)
        result = run_cli(self.tmp, "--yaml", str(cfg))
        self.assertNotIn("end_lines", result.stdout)

    def test_check_function(self):
        self.assertIsNone(repmark.check_line_counts(["a", "b"], ["x", "y"]))
        self.assertIn("1 side_lines but 3 end_lines", repmark.check_line_counts(["a"], ["x", "y", "z"]))


# --- 7. UV coordinates in bbox JSON ----------------------------------------
class UvExportTests(CliTestCase):
    def test_bbox_to_uv_flips_v_for_blender(self):
        self.assertEqual(repmark.bbox_to_uv((0, 0, 512, 256), 512, 512), [0.0, 0.5, 1.0, 1.0])
        self.assertEqual(repmark.bbox_to_uv((128, 256, 256, 512), 512, 512), [0.25, 0.0, 0.5, 0.5])

    def test_json_contains_canvas_and_uvs(self):
        cfg = write_config(self.tmp)
        result = run_cli(self.tmp, "--yaml", str(cfg))
        self.assertEqual(result.returncode, 0, result.stdout)
        data = json.loads((self.tmp / "out" / "test_bboxes.json").read_text(encoding="utf-8"))

        self.assertEqual(data["canvas"]["width"], 512)
        self.assertEqual(data["canvas"]["height"], 512)
        self.assertEqual(data["canvas"]["uv_origin"], "bottom-left")
        self.assertEqual(len(data["side"]), 2)
        self.assertEqual(len(data["end"]), 2)

        for entry in data["side"]:
            self.assertEqual(entry["uv"], repmark.bbox_to_uv(entry["bbox"], 512, 512))
        for entry in data["end"]:
            self.assertEqual(entry["uv_top"], repmark.bbox_to_uv(entry["bbox_top"], 512, 512))
            self.assertEqual(entry["uv_bottom"], repmark.bbox_to_uv(entry["bbox_bottom"], 512, 512))
            # Combined UV covers both stacked parts.
            u0, v0, u1, v1 = entry["uv"]
            self.assertLessEqual(u0, min(entry["uv_top"][0], entry["uv_bottom"][0]))
            self.assertLessEqual(v0, min(entry["uv_top"][1], entry["uv_bottom"][1]))
            self.assertGreaterEqual(u1, max(entry["uv_top"][2], entry["uv_bottom"][2]))
            self.assertGreaterEqual(v1, max(entry["uv_top"][3], entry["uv_bottom"][3]))
            for value in entry["uv"]:
                self.assertTrue(0.0 <= value <= 1.0)

        # The first side mark is near the top of the image, so its V is near 1.
        self.assertGreater(data["side"][0]["uv"][3], 0.9)

    def test_json_bbox_matches_rendered_pixels(self):
        """Every side bbox should contain opaque text pixels."""
        cfg = write_config(self.tmp)
        self.assertEqual(run_cli(self.tmp, "--yaml", str(cfg)).returncode, 0)
        data = json.loads((self.tmp / "out" / "test_bboxes.json").read_text(encoding="utf-8"))
        with Image.open(self.tmp / "out" / "test.png") as im:
            alpha = im.getchannel("A")
            for entry in data["side"]:
                self.assertIsNotNone(alpha.crop(tuple(entry["bbox"])).getbbox(), entry)


# --- Existing behaviour: CSV, formatting, validation -----------------------
class RosterTests(CliTestCase):
    def write_csv(self, text: str) -> Path:
        path = self.tmp / "roster.csv"
        path.write_text(text, encoding="utf-8")
        return path

    def test_one_column_with_header(self):
        path = self.write_csv("number\n998235\n998375\n")
        self.assertEqual(repmark.read_roster_csv(path, "NS"), [("NS", "998235"), ("NS", "998375")])

    def test_one_column_no_header(self):
        path = self.write_csv("998235\n# comment\n\n998375\n")
        self.assertEqual(repmark.read_roster_csv(path, "NS"), [("NS", "998235"), ("NS", "998375")])

    def test_prefix_column_with_header(self):
        path = self.write_csv("prefix,number\nsou,123456\n,998235\n")
        self.assertEqual(repmark.read_roster_csv(path, "NS"), [("SOU", "123456"), ("NS", "998235")])

    def test_prefix_column_no_header(self):
        path = self.write_csv("CR,4500\nCR,4501\n")
        self.assertEqual(repmark.read_roster_csv(path, "NS"), [("CR", "4500"), ("CR", "4501")])

    def test_empty_roster_errors(self):
        path = self.write_csv("number\n")
        with self.assertRaises(ValueError):
            repmark.read_roster_csv(path, "NS")

    def test_csv_cli_route(self):
        roster = self.write_csv("number\n998235\n998375\n998369\n")
        cfg = write_config(self.tmp)
        result = run_cli(self.tmp, "--yaml", str(cfg), "--csv", str(roster), "--prefix", "NS")
        self.assertEqual(result.returncode, 0, result.stdout)
        data = json.loads((self.tmp / "out" / "test_bboxes.json").read_text(encoding="utf-8"))
        self.assertEqual([e["text"] for e in data["side"]], ["998 235", "998 375", "998 369"])
        self.assertEqual([e["text"] for e in data["end"]], ["NS 998235", "NS 998375", "NS 998369"])


class FormattingTests(unittest.TestCase):
    def test_format_side_number(self):
        self.assertEqual(repmark.format_side_number("998235"), "998 235")
        self.assertEqual(repmark.format_side_number("998 235"), "998 235")
        self.assertEqual(repmark.format_side_number("4500"), "4 500")
        self.assertEqual(repmark.format_side_number("123"), "123")

    def test_reporting_marks_to_lines(self):
        self.assertEqual(
            repmark.reporting_marks_to_lines([("NS", "998235")]),
            (["998 235"], [{"value": "NS 998235", "stacked": True}]),
        )


class ValidationTests(unittest.TestCase):
    def valid(self, **overrides):
        import contextlib, io
        cfg = {**repmark.DEFAULT_CONFIG, **overrides}
        with contextlib.redirect_stdout(io.StringIO()):
            return repmark.validate_config(cfg)

    def test_defaults_are_valid(self):
        self.assertTrue(self.valid())

    def test_bad_values_rejected(self):
        self.assertFalse(self.valid(width=0))
        self.assertFalse(self.valid(bgrgba="0,0,0"))
        self.assertFalse(self.valid(font_color=[0, 0, 0, 300]))
        self.assertFalse(self.valid(end_lines=[{"value": ""}]))
        self.assertFalse(self.valid(font_stroke_width=-1))

    def test_defaults_not_mutated_by_cli_without_yaml(self):
        before = json.dumps(repmark.DEFAULT_CONFIG, sort_keys=True)
        with tempfile.TemporaryDirectory() as tmp:
            roster = Path(tmp) / "r.csv"
            roster.write_text("998235\n", encoding="utf-8")
            old_argv = sys.argv
            sys.argv = ["repmark", "--csv", str(roster)]
            try:
                import contextlib, io, os
                cwd = os.getcwd()
                os.chdir(tmp)
                try:
                    with contextlib.redirect_stdout(io.StringIO()):
                        repmark.main()
                finally:
                    os.chdir(cwd)
            finally:
                sys.argv = old_argv
        self.assertEqual(json.dumps(repmark.DEFAULT_CONFIG, sort_keys=True), before)


if __name__ == "__main__":
    unittest.main()
