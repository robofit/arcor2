import uuid

from arcor2 import package_version


def version() -> str:
    return package_version(__name__)


def get_id() -> int:
    return uuid.uuid4().int % 2 ** 32
