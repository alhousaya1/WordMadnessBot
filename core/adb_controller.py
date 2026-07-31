"""
==========================================================
Word Madness Bot
ADB Controller
==========================================================
"""

import subprocess
import time
from pathlib import Path

from config.logger import logger
from config.config import (
    ADB_COMMAND,
    SCREENSHOT_FOLDER,
    ADB_TIMEOUT
)


class ADBController:

    def __init__(self):

        self.device = None
        self.model = ""
        self.android_version = ""
        self.width = 0
        self.height = 0
        self.density = 0

    # -----------------------------------------------------

    def run(self, command):

        cmd = [ADB_COMMAND]

        cmd.extend(command)

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=ADB_TIMEOUT
        )

        return result.stdout.strip()

    # -----------------------------------------------------

    def shell(self, command):

        return self.run(["shell"] + command.split())

    # -----------------------------------------------------

    def connect(self):

        logger.info("Searching for Android devices...")

        output = self.run(["devices"])

        lines = output.splitlines()[1:]

        devices = []

        for line in lines:

            if "\tdevice" in line:

                serial = line.split()[0]

                devices.append(serial)

        if len(devices) == 0:

            raise Exception("No Android device connected.")

        self.device = devices[0]

        logger.success(f"Connected to {self.device}")

        return True

    # -----------------------------------------------------

    def read_phone_information(self):

        logger.info("Reading phone information...")

        self.model = self.shell(
            "getprop ro.product.model"
        )

        self.android_version = self.shell(
            "getprop ro.build.version.release"
        )

        size = self.shell(
            "wm size"
        )

        density = self.shell(
            "wm density"
        )

        size = size.replace("Physical size:", "").strip()

        width, height = size.split("x")

        self.width = int(width)

        self.height = int(height)

        density = density.replace(
            "Physical density:",
            ""
        ).strip()

        self.density = int(density)

        logger.success(self.model)

        logger.success(f"Android {self.android_version}")

        logger.success(
            f"{self.width} x {self.height}"
        )

        logger.success(
            f"Density {self.density}"
        )

    # -----------------------------------------------------

    def screenshot(self):

        logger.info("Taking screenshot...")

        SCREENSHOT_FOLDER.mkdir(
            parents=True,
            exist_ok=True
        )

        filename = (
            SCREENSHOT_FOLDER /
            "latest.png"
        )

        with open(filename, "wb") as image:

            process = subprocess.Popen(

                [
                    ADB_COMMAND,
                    "exec-out",
                    "screencap",
                    "-p"
                ],

                stdout=image

            )

            process.wait()

        logger.success("Screenshot saved.")

        return filename

    # -----------------------------------------------------

    def tap(self, x, y):

        logger.info(f"Tap ({x},{y})")

        self.shell(
            f"input tap {x} {y}"
        )

    # -----------------------------------------------------

    def swipe(
        self,
        x1,
        y1,
        x2,
        y2,
        duration=150
    ):

        logger.info(
            f"Swipe ({x1},{y1}) -> ({x2},{y2})"
        )

        self.shell(

            f"input swipe "
            f"{x1} {y1} "
            f"{x2} {y2} "
            f"{duration}"

        )

    # -----------------------------------------------------

    def sleep(self, seconds):

        time.sleep(seconds)