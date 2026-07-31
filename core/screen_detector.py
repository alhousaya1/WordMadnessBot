"""
==========================================================
Word Madness Bot
Screen Detector
==========================================================
"""

from pathlib import Path

import cv2

from config.logger import logger


class ScreenDetector:

    def __init__(self):

        self.image = None

    # -----------------------------------------------------

    def load_image(self, image_path):

        image_path = Path(image_path)

        if not image_path.exists():

            raise FileNotFoundError(image_path)

        self.image = cv2.imread(str(image_path))

        if self.image is None:

            raise Exception("Could not read screenshot.")

        logger.success("Screenshot loaded.")

        return self.image

    # -----------------------------------------------------

    def get_width(self):

        return self.image.shape[1]

    # -----------------------------------------------------

    def get_height(self):

        return self.image.shape[0]

    # -----------------------------------------------------

    def print_information(self):

        logger.info(
            f"Image Size : {self.get_width()} x {self.get_height()}"
        )

    # -----------------------------------------------------

    def save_debug(self, filename):

        cv2.imwrite(filename, self.image)

        logger.success(f"Debug image saved : {filename}")