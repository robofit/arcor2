import os

from arcor2 import package_version

CALIBRATION_URL = os.getenv("ARCOR2_CALIBRATION_URL", "http://localhost:5014")
SERVICE_NAME = "ARCOR2 Calibration Service"


def version() -> str:
    return package_version(__name__)
