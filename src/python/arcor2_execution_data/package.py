import os
import sys
from datetime import datetime, timezone

from dataclasses_jsonschema import ValidationError

from arcor2.data.execution import PackageMeta

"""
Functions used by the main script itself (Resources class) or Execution service.
"""

PROJECT_PATH_NAME = "ARCOR2_PROJECT_PATH"

try:
    PROJECT_PATH = os.environ[PROJECT_PATH_NAME]
except KeyError:
    sys.exit(f"'{PROJECT_PATH_NAME}' env. variable not set.")


def get_package_meta_path(package_id: str) -> str:

    return os.path.join(PROJECT_PATH, package_id, "package.json")


def read_package_meta(package_id: str) -> PackageMeta:

    try:
        with open(get_package_meta_path(package_id)) as pkg_file:
            return PackageMeta.from_json(pkg_file.read())
    except (IOError, ValidationError, ValueError):  # TODO rather propagate as Arcor2Exception
        return PackageMeta("N/A", datetime.fromtimestamp(0, tz=timezone.utc))


def write_package_meta(package_id: str, meta: PackageMeta) -> None:

    with open(get_package_meta_path(package_id), "w") as pkg_file:
        pkg_file.write(meta.to_json())
