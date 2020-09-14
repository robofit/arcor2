import os

from arcor2 import package_version

SERVICE_NAME = "ARCOR2 Build Service"
PORT = int(os.getenv("ARCOR2_BUILD_PORT", 5008))


def version() -> str:
    return package_version(__name__)
