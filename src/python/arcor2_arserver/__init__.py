from arcor2 import package_version
from arcor2.logging import get_aiologger

logger = get_aiologger("ARServer")


def version() -> str:
    return package_version(__name__)
