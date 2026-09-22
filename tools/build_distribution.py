#!/usr/bin/env python
"""Build a Windows distribution ZIP for RepMark."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
RELEASE = ROOT / "release"


def read_version() -> str:
    return (ROOT / "VERSION").read_text(encoding="utf-8").strip()


def run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess[str]:
    print("$ " + subprocess.list2cmdline(cmd))
    result = subprocess.run(cmd, cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, **kwargs)
    print(result.stdout)
    if result.returncode != 0:
        raise SystemExit(result.returncode)
    return result


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git_value(args: list[str]) -> str:
    try:
        result = subprocess.run(["git", *args], cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        if result.returncode == 0:
            return result.stdout.strip()
    except OSError:
        pass
    return "unknown"


def copy_required_file(source: Path, target: Path) -> None:
    if not source.exists():
        raise SystemExit(f"Required release file is missing: {source}")
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)


def build_exes() -> None:
    run(["cmd.exe", "/c", "build_windows_gui.bat"], timeout=900)


def verify_exes(version: str, release_dir: Path) -> None:
    cli = release_dir / "repmark.exe"
    gui = release_dir / "RepMarkStudio.exe"
    cli_version = run([str(cli), "--version"], timeout=60).stdout.strip()
    if cli_version != f"repmark {version}":
        raise SystemExit(f"Unexpected CLI version: {cli_version!r}; expected repmark {version}")
    run([str(gui), "--self-test"], timeout=90)


def write_manifest(version: str, release_dir: Path, zip_path: Path | None = None) -> None:
    files = []
    for path in sorted(p for p in release_dir.rglob("*") if p.is_file()):
        rel = path.relative_to(release_dir).as_posix()
        if rel == "RELEASE_MANIFEST.json":
            continue
        files.append({
            "path": rel,
            "size": path.stat().st_size,
            "sha256": sha256(path),
        })
    manifest = {
        "name": "RepMark",
        "version": version,
        "built_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "git_commit": git_value(["rev-parse", "--short", "HEAD"]),
        "git_branch": git_value(["branch", "--show-current"]),
        "git_dirty": bool(git_value(["status", "--porcelain"])),
        "zip_file": zip_path.name if zip_path else None,
        "files": files,
    }
    (release_dir / "RELEASE_MANIFEST.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def write_release_notes(version: str, release_dir: Path) -> None:
    text = f"""RepMark {version} Windows Distribution

Run RepMarkStudio.exe for the GUI.
Run repmark.exe from a terminal for command-line generation.

Included files:
- RepMarkStudio.exe: GUI application
- repmark.exe: command-line backend
- config.yaml: editable starter configuration
- sample_roster.csv: example roster import file
- fonts/: font folder used by config.yaml and the GUI font picker
- README.md: usage notes
- RELEASE_MANIFEST.json: file sizes and SHA256 checksums

Generated decals default to the out/ folder beside the running EXE.
"""
    (release_dir / "RELEASE_NOTES.txt").write_text(text, encoding="utf-8")


def assemble_release(version: str) -> tuple[Path, Path]:
    release_name = f"RepMark-{version}-win64"
    release_dir = RELEASE / release_name
    zip_path = RELEASE / f"{release_name}.zip"
    if release_dir.exists():
        shutil.rmtree(release_dir)
    if zip_path.exists():
        zip_path.unlink()
    release_dir.mkdir(parents=True)

    copy_required_file(DIST / "repmark.exe", release_dir / "repmark.exe")
    copy_required_file(DIST / "RepMarkStudio.exe", release_dir / "RepMarkStudio.exe")
    for filename in ("VERSION", "config.yaml", "sample_roster.csv", "README.md"):
        copy_required_file(ROOT / filename, release_dir / filename)
    shutil.copytree(ROOT / "fonts", release_dir / "fonts")
    shutil.copytree(ROOT / "assets", release_dir / "assets")
    write_release_notes(version, release_dir)
    write_manifest(version, release_dir)
    return release_dir, zip_path


def zip_release(release_dir: Path, zip_path: Path) -> None:
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for path in sorted(p for p in release_dir.rglob("*") if p.is_file()):
            zf.write(path, path.relative_to(release_dir.parent))
    # Add the ZIP hash after creating it; useful for web/download checks.
    checksum = f"{sha256(zip_path)}  {zip_path.name}\n"
    (zip_path.with_suffix(zip_path.suffix + ".sha256")).write_text(checksum, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build RepMark Windows release ZIP.")
    parser.add_argument("--skip-build", action="store_true", help="Package existing dist EXEs instead of rebuilding them first.")
    args = parser.parse_args()

    version = read_version()
    print(f"Building RepMark distribution {version}")
    if not args.skip_build:
        build_exes()
    release_dir, zip_path = assemble_release(version)
    verify_exes(version, release_dir)
    write_manifest(version, release_dir, zip_path)
    zip_release(release_dir, zip_path)
    print(f"Release folder: {release_dir}")
    print(f"Release ZIP:    {zip_path}")
    print(f"SHA256 file:    {zip_path.with_suffix(zip_path.suffix + '.sha256')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
