import importlib
import inspect
import pkgutil
from typing import Dict

from dataclasses_jsonschema import JsonSchemaMixin, ValidationError
from dataclasses_jsonschema.apispec import DataclassesPlugin, _schema_reference

from arcor2.exceptions import Arcor2Exception


class DataException(Arcor2Exception):
    pass


def resolve_schema_refs(self, data: Dict) -> None:

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

    for _, module_name, _ in pkgutil.iter_modules(data.__path__):  # type: ignore

        module = importlib.import_module(f"{data.__name__}.{module_name}")

        for _, obj in inspect.getmembers(module, inspect.isclass):

            if not issubclass(obj, JsonSchemaMixin) or obj is JsonSchemaMixin or inspect.isabstract(obj):
                continue

            try:
                obj.from_dict({})
            except ValidationError:
                pass
