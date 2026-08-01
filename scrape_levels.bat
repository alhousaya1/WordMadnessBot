@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    py -3 -m venv .venv
    if errorlevel 1 exit /b 1
)

".venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 exit /b 1

".venv\Scripts\python.exe" -m pip install "requests>=2.32,<3" "beautifulsoup4>=4.12,<5"
if errorlevel 1 exit /b 1

".venv\Scripts\python.exe" scrape_levels.py
exit /b %errorlevel%
