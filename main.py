from core.screen_detector import ScreenDetector
from core.letter_detector import LetterDetector
"""
==========================================================
Word Madness Bot
Main Entry Point
==========================================================
"""

from config.config import (
    BOT_NAME,
    BOT_VERSION,
    create_project_folders
)

from config.logger import logger
from core.adb_controller import ADBController


def print_banner():

    print()
    print("=" * 50)
    print(f"{BOT_NAME} v{BOT_VERSION}")
    print("=" * 50)
    print()


def main():

    print_banner()

    create_project_folders()

    adb = ADBController()

    try:

        adb.connect()

        adb.read_phone_information()

        screenshot = adb.screenshot()
        detector = ScreenDetector()
        detector.load_image(screenshot)
        detector.print_information()
        letter_detector = LetterDetector()
        letter_detector.detect_circle(detector.image)

        logger.success("Foundation test completed.")
        logger.info(f"Screenshot saved to: {screenshot}")

    except Exception as error:

        logger.error(str(error))

    print()
    input("Press ENTER to exit...")


if __name__ == "__main__":
    main()