import os

from arcor2 import package_version

_ROOT = os.path.abspath(os.path.dirname(__file__))


def version() -> str:
    return package_version(__name__)
