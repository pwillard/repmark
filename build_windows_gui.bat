@echo off
setlocal
cd /d "%~dp0"

where uvx >nul 2>nul
if errorlevel 1 (
  echo uvx was not found. Install uv or replace this command with: python -m PyInstaller ...
  exit /b 1
)

call build_windows_cli.bat
if errorlevel 1 exit /b %errorlevel%

uvx --with pillow --with pyyaml pyinstaller ^
  --noconfirm ^
  --clean ^
  --onefile ^
  --windowed ^
  --name RepMarkStudio ^
  --icon "assets\RepMark_RSS.ico" ^
  --add-data "assets;assets" ^
  --add-data "VERSION;." ^
  --add-data "config.yaml;." ^
  --add-data "sample_roster.csv;." ^
  --add-data "fonts;fonts" ^
  --add-data "repmark.py;." ^
  --add-binary "dist\repmark.exe;." ^
  repmark_gui.py

if errorlevel 1 exit /b %errorlevel%

echo.
echo Built: %CD%\dist\RepMarkStudio.exe
