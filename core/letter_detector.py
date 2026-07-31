"""
==========================================================
Word Madness Bot
Letter Circle Detector
==========================================================
"""

import cv2

from config.logger import logger
from config.config import DEBUG_FOLDER


class LetterDetector:

    def __init__(self):
        pass

    def detect_circle(self, image):

        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        circles = cv2.HoughCircles(
            gray,
            cv2.HOUGH_GRADIENT,
            dp=1.2,
            minDist=500,
            param1=100,
            param2=40,
            minRadius=250,
            maxRadius=800
        )

        if circles is None:

            logger.warning("Letter circle not found.")

            return None

        circles = circles[0]

        largest = max(circles, key=lambda c: c[2])

        x = int(largest[0])
        y = int(largest[1])
        r = int(largest[2])

        logger.success(
            f"Letter circle detected ({x}, {y}) radius={r}"
        )

        output = image.copy()

        cv2.circle(
            output,
            (x, y),
            r,
            (0, 255, 0),
            4
        )

        DEBUG_FOLDER.mkdir(
            parents=True,
            exist_ok=True
        )

        filename = DEBUG_FOLDER / "letter_circle_detected.png"

        cv2.imwrite(str(filename), output)

        logger.success(
            f"Debug image saved: {filename}"
        )

        return x, y, r