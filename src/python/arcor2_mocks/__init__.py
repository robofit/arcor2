import os

from arcor2 import package_version

PROJECT_SERVICE_NAME = "ARCOR2 Project mock Web API"
PROJECT_PORT = int(os.getenv("ARCOR2_PROJECT_SERVICE_MOCK_PORT", 5012))

ASSET_SERVICE_NAME = "ARCOR2 Asset mock Web API"
ASSET_PORT = int(os.getenv("ARCOR2_ASSET_SERVICE_MOCK_PORT", 5017))


def version() -> str:
    return package_version(__name__)
