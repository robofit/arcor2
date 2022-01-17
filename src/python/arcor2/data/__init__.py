import importlib
import inspect
import pkgutil
from typing import TYPE_CHECKING

import dataclasses_jsonschema
import orjson
from dataclasses_jsonschema import JsonSchemaMixin, ValidationError
from dataclasses_jsonschema.apispec import DataclassesPlugin, _schema_reference

from arcor2.exceptions import Arcor2Exception


class DataException(Arcor2Exception):
    pass


if not TYPE_CHECKING:

    # monkey-patch dataclasses_jsonschema to use orjson instead of json

    @classmethod
    def from_json(
        cls: type[dataclasses_jsonschema.T], data: str, validate: bool = True, **json_kwargs
    ) -> dataclasses_jsonschema.T:
        return cls.from_dict(orjson.loads(data), validate)

    def to_json(self, omit_none: bool = True, validate: bool = False, **json_kwargs) -> str:
        return orjson.dumps(self.to_dict(omit_none, validate), **json_kwargs).decode()

    JsonSchemaMixin.from_json = from_json
    JsonSchemaMixin.to_json = to_json


def resolve_schema_refs(self, data: dict) -> None:

    if "schema" in data:

        if "$ref" in data["schema"]:
            data["schema"]["$ref"] = _schema_reference(data["schema"]["$ref"], self._schema_type)
        elif "items" in data["schema"] and "$ref" in data["schema"]["items"]:
            data["schema"]["items"]["$ref"] = _schema_reference(data["schema"]["items"]["$ref"], self._schema_type)
    else:
        for key in data:
            if isinstance(data[key], dict):
                self.resolve_schema_refs(data[key])


# monkey patch to solve https://github.com/s-knibbs/dataclasses-jsonschema/issues/126
DataclassesPlugin.resolve_schema_refs = resolve_schema_refs  # type: ignore


def compile_json_schemas() -> None:
    """
    Force compilation of json schema (otherwise it might cause troubles later when executed in parallel)
    :return:
    """

    from arcor2 import data

    for _, module_name, _ in pkgutil.iter_modules(data.__path__):

        module = importlib.import_module(f"{data.__name__}.{module_name}")

        for _, obj in inspect.getmembers(module, inspect.isclass):

            if not issubclass(obj, JsonSchemaMixin) or obj is JsonSchemaMixin or inspect.isabstract(obj):
                continue

            try:
                obj.from_dict({})
            except ValidationError:
                pass
