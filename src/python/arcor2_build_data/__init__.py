import os

from arcor2 import package_version

SERVICE_NAME = "ARCOR2 Build Service"
URL = os.getenv("ARCOR2_BUILD_URL", "http://0.0.0.0:5008")


def version() -> str:
    return package_version(__name__)
