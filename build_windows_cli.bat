@echo off
setlocal
cd /d "%~dp0"

where uvx >nul 2>nul
if errorlevel 1 (
  echo uvx was not found. Install uv or replace this command with: python -m PyInstaller ...
  exit /b 1
)

uvx --with pillow --with pyyaml pyinstaller ^
  --noconfirm ^
  --clean ^
  --onefile ^
  --console ^
  --name repmark ^
  --add-data "VERSION;." ^
  --add-data "config.yaml;." ^
  --add-data "sample_roster.csv;." ^
  --add-data "fonts;fonts" ^
  repmark.py

if errorlevel 1 exit /b %errorlevel%

echo.
echo Built: %CD%\dist\repmark.exe
