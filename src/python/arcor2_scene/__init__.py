import os

from arcor2 import package_version

SCENE_PORT = int(os.getenv("ARCOR2_SCENE_SERVICE_PORT", 5013))
SCENE_SERVICE_NAME = "ARCOR2 Scene Web API"


def version() -> str:
    return package_version(__name__)
