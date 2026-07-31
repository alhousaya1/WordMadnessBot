@echo off
title Installing Word Madness Bot

cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    py -3.11 -m venv .venv
    if errorlevel 1 exit /b 1
)

call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
if errorlevel 1 exit /b 1

word-madness-bot validate-config
if errorlevel 1 exit /b 1
word-madness-bot validate-database
if errorlevel 1 exit /b 1

echo Installation and validation completed successfully.
