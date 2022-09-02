import os

from arcor2 import package_version

PROJECT_PORT = int(os.getenv("ARCOR2_PROJECT_SERVICE_MOCK_PORT", 5012))
PROJECT_SERVICE_NAME = "ARCOR2 Project mock Web API"


def version() -> str:
    return package_version(__name__)
