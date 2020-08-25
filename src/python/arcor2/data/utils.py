import inspect
from types import ModuleType
from typing import Iterable

from apispec import APISpec  # type: ignore
from apispec.exceptions import DuplicateComponentNameError  # type: ignore
from apispec_webframeworks.flask import FlaskPlugin  # type: ignore
from dataclasses_jsonschema import JsonSchemaMixin
from dataclasses_jsonschema.apispec import DataclassesPlugin


def generate_swagger(service_name: str, version: str, modules: Iterable[ModuleType]) -> str:

    # Create an APISpec
    spec = APISpec(
        title=f"{service_name} Data Models",
        version=version,
        openapi_version="3.0.2",
        plugins=[FlaskPlugin(), DataclassesPlugin()],
    )

    for module in modules:
        for _, obj in inspect.getmembers(module):

            if not inspect.isclass(obj) or not issubclass(obj, JsonSchemaMixin) or obj == JsonSchemaMixin:
                continue

            try:
                spec.components.schema(obj.__name__, schema=obj)
            except DuplicateComponentNameError:
                continue

    return spec.to_yaml()
