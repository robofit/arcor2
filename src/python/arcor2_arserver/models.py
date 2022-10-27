import inspect
from enum import Enum

from apispec import APISpec
from apispec.exceptions import DuplicateComponentNameError
from apispec_webframeworks.flask import FlaskPlugin
from dataclasses_jsonschema import JsonSchemaMixin
from dataclasses_jsonschema.apispec import DataclassesPlugin

from arcor2.data.events import Event
from arcor2.data.rpc.common import RPC


def _rename_childs(obj: type[JsonSchemaMixin] | type[Enum]) -> None:

    for _, child_obj in inspect.getmembers(obj, inspect.isclass):

        if issubclass(child_obj, (JsonSchemaMixin, Enum)):

            if hasattr(child_obj, "__renamed__"):
                continue

            if "." in child_obj.__qualname__:
                child_obj.__name__ = "".join(child_obj.__qualname__.split("."))
                child_obj.__renamed__ = None

            _rename_childs(child_obj)


def _add_to_spec(spec, obj) -> None:

    try:
        spec.components.schema(obj.__name__, schema=obj)
    except DuplicateComponentNameError:
        pass


def generate_openapi(service_name: str, version: str, rpcs: list[type[RPC]], events: list[type[Event]]) -> str:
    """Generate OpenAPI models from RPCs and events.

    Be aware: it modifies __name__ attribute!
    """

    # Create an APISpec
    spec = APISpec(
        title=f"{service_name} Data Models",
        version=version,
        openapi_version="3.0.2",
        plugins=[FlaskPlugin(), DataclassesPlugin()],
    )

    for obj in events:

        if obj is Event:
            continue

        _rename_childs(obj)

    for rpc in rpcs:

        if rpc is RPC:
            continue

        for cls in (rpc.Request, rpc.Response):

            cls.__name__ = rpc.__name__ + cls.__name__
            _rename_childs(cls)

    for obj in events:
        _add_to_spec(spec, obj)
    for rpc in rpcs:
        for cls in (rpc.Request, rpc.Response):
            _add_to_spec(spec, cls)

    return spec.to_yaml()
