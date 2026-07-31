"""
==========================================================
Word Madness Bot
Configuration File
==========================================================
"""

from pathlib import Path

# ==========================================================
# Project Information
# ==========================================================

BOT_NAME = "Word Madness Bot"
BOT_VERSION = "1.0"

# ==========================================================
# Project Paths
# ==========================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent

DATABASE_FOLDER = PROJECT_ROOT / "database"
DEBUG_FOLDER = PROJECT_ROOT / "debug"
LOG_FOLDER = PROJECT_ROOT / "logs"
SCREENSHOT_FOLDER = PROJECT_ROOT / "screenshots"
TEMPLATE_FOLDER = PROJECT_ROOT / "templates"

# ==========================================================
# ADB
# ==========================================================

ADB_COMMAND = "adb"

# ==========================================================
# Timing
# ==========================================================

HOME_SCREEN_WAIT = 2.0
LEVEL_LOAD_WAIT = 2.0
WORD_DELAY = 0.20
SWIPE_SPEED = 150
ADB_TIMEOUT = 15

# Wait exactly this long before solving
LEVEL_START_DELAY = 10

# ==========================================================
# OCR
# ==========================================================

TESSERACT_COMMAND = "tesseract"

OCR_LANGUAGE = "eng"

# ==========================================================
# Debug
# ==========================================================

DEBUG_MODE = True
SAVE_SCREENSHOTS = True
SAVE_FAILED_IMAGES = True

# ==========================================================
# Image Matching
# ==========================================================

HOME_TEMPLATE_THRESHOLD = 0.90
LEVEL_TEMPLATE_THRESHOLD = 0.90
LETTER_THRESHOLD = 0.85

# ==========================================================
# Logging
# ==========================================================

LOG_LEVEL = "INFO"

# ==========================================================
# Create folders automatically
# ==========================================================

def create_project_folders():

    folders = [

        DATABASE_FOLDER,
        DEBUG_FOLDER,
        LOG_FOLDER,
        SCREENSHOT_FOLDER,
        TEMPLATE_FOLDER

    ]

    for folder in folders:
        folder.mkdir(parents=True, exist_ok=True)