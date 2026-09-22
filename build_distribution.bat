@echo off
setlocal
cd /d "%~dp0"

python tools\build_distribution.py %*
exit /b %errorlevel%
