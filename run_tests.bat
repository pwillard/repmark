@echo off
setlocal
cd /d "%~dp0"

where uv >nul 2>nul
if errorlevel 1 (
  echo uv was not found. Install uv or run: python -m unittest discover -s tests -v
  exit /b 1
)

uv run --no-project --with pillow --with pyyaml python -m unittest discover -s tests -v %*
exit /b %errorlevel%
