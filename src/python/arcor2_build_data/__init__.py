import os
from dataclasses import dataclass, field

from dataclasses_jsonschema import DEFAULT_SCHEMA_TYPE, FieldMeta, JsonSchemaMixin

from arcor2 import package_version

SERVICE_NAME = "Build"
URL = os.getenv("ARCOR2_BUILD_URL", "http://0.0.0.0:5008")
DEPENDENCIES: dict[str, str] = {"Project": "1.0.0"}


@dataclass
class ImportResult(JsonSchemaMixin):
    """Info about the package that was just imported."""

    # TODO this should be rather snake_case and automatically converted to camelCase when generating OpenAPI
    sceneId: str = field(
        metadata=FieldMeta(
            schema_type=DEFAULT_SCHEMA_TYPE,
            description="Id of imported scene.",
        ).as_dict
    )
    projectId: str = field(
        metadata=FieldMeta(
            schema_type=DEFAULT_SCHEMA_TYPE,
            description="Id of imported project.",
        ).as_dict
    )


def version() -> str:
    return package_version(__name__)
