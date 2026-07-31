@echo off
title Word Madness Bot

cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Word Madness Bot is not installed. Run INSTALL.bat first.
    exit /b 1
)

call .venv\Scripts\activate.bat
word-madness-bot run
exit /b %errorlevel%
