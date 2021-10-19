import os
from dataclasses import dataclass

from dataclasses_jsonschema import JsonSchemaMixin

from arcor2 import package_version

SERVICE_NAME = "ARCOR2 Build Service"
URL = os.getenv("ARCOR2_BUILD_URL", "http://0.0.0.0:5008")


@dataclass
class ImportResult(JsonSchemaMixin):
    """Info on the package that was just imported."""

    # TODO this should be rather snake_case and automatically converted to camelCase when generating OpenAPI
    sceneId: str
    projectId: str


def version() -> str:
    return package_version(__name__)
