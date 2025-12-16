import os

from arcor2 import package_version

STORAGE_PORT = int(os.getenv("ARCOR2_STORAGE_SERVICE_PORT", 10000))
STORAGE_DB_PATH = os.getenv("ARCOR2_STORAGE_DB_PATH", "/data/arcor2_storage.sqlite")
STORAGE_SERVICE_NAME = "ARCOR2 Storage Service"


def version() -> str:
    return package_version(__name__)
