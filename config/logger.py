"""
==========================================================
Word Madness Bot
Logger
==========================================================
"""

import logging
from datetime import datetime
from pathlib import Path

from config.config import LOG_FOLDER


class BotLogger:

    def __init__(self):

        LOG_FOLDER.mkdir(parents=True, exist_ok=True)

        log_name = datetime.now().strftime("%Y-%m-%d_%H-%M-%S") + ".log"

        log_file = LOG_FOLDER / log_name

        self.logger = logging.getLogger("WordMadnessBot")
        self.logger.setLevel(logging.INFO)

        if self.logger.handlers:
            self.logger.handlers.clear()

        formatter = logging.Formatter(
            "[%(asctime)s] %(levelname)s : %(message)s",
            "%H:%M:%S"
        )

        # Console output
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)

        # File output
        file_handler = logging.FileHandler(
            log_file,
            encoding="utf-8"
        )
        file_handler.setFormatter(formatter)

        self.logger.addHandler(console_handler)
        self.logger.addHandler(file_handler)

    def info(self, message):
        self.logger.info(message)

    def warning(self, message):
        self.logger.warning(message)

    def error(self, message):
        self.logger.error(message)

    def success(self, message):
        self.logger.info("✓ " + message)


# Global logger
logger = BotLogger()