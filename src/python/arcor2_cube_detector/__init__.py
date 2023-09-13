import os

from arcor2 import package_version

_ROOT = os.path.abspath(os.path.dirname(__file__))


def version() -> str:
    return package_version(__name__)


def get_data(path: str) -> str:
    return os.path.join(_ROOT, "data", path)
