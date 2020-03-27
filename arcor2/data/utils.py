import inspect

from apispec import APISpec  # type: ignore
from apispec.exceptions import DuplicateComponentNameError  # type: ignore
from apispec_webframeworks.flask import FlaskPlugin  # type: ignore
from dataclasses_jsonschema import JsonSchemaMixin
from dataclasses_jsonschema.apispec import DataclassesPlugin

import arcor2
import arcor2.data.common
import arcor2.data.events
import arcor2.data.object_type
from arcor2.data import rpc


def generate_swagger() -> str:

    # Create an APISpec
    spec = APISpec(
        title="ARCOR2 Data Models",
        version=arcor2.api_version(),
        openapi_version="3.0.2",
        plugins=[FlaskPlugin(), DataclassesPlugin()],
    )

    # TODO avoid explicit naming of all sub-modules in rpc module
    for module in (arcor2.data.common, arcor2.data.object_type, rpc.common, rpc.execution, rpc.objects,
                   rpc.robot, rpc.scene, rpc.project, rpc.services,
                   rpc.storage, arcor2.data.events):
        for name, obj in inspect.getmembers(module):

            if not inspect.isclass(obj) or not issubclass(obj, JsonSchemaMixin) or obj == JsonSchemaMixin:
                continue

            try:
                spec.components.schema(obj.__name__, schema=obj)
            except DuplicateComponentNameError:
                continue

    return spec.to_yaml()
