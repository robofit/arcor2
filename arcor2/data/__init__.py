import inspect
import pkgutil
import importlib

from dataclasses_jsonschema import JsonSchemaMixin, ValidationError

from arcor2.exceptions import Arcor2Exception


class DataException(Arcor2Exception):
    pass


def compile_json_schemas():
    """
    Force compilation of json schema (otherwise it might cause troubles later when executed in parallel)
    :return:
    """

    from arcor2 import data

    for _, module_name, _ in pkgutil.iter_modules(data.__path__):  # type: ignore

        module = importlib.import_module(f"{data.__name__}.{module_name}")

        for _, obj in inspect.getmembers(module, inspect.isclass):

            if not issubclass(obj, JsonSchemaMixin) or obj is JsonSchemaMixin:
                continue

            try:
                obj.from_dict({})
            except ValidationError:
                pass
