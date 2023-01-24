import logging
import os

from arcor2 import env, package_version

_ROOT = os.path.abspath(os.path.dirname(__file__))

ARCOR2_KINECT_AZURE_LOG_LEVEL = logging.DEBUG if env.get_bool("ARCOR2_KINECT_AZURE_DEBUG") else logging.INFO


def version() -> str:
    return package_version(__name__)


def get_data(path: str) -> str:
    return os.path.join(_ROOT, "data", path)
