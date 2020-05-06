import inspect
import sys

from dataclasses_jsonschema import JsonSchemaMixin, ValidationError

from arcor2.exceptions import Arcor2Exception


class DataException(Arcor2Exception):
    pass


# force compilation of json schema (otherwise it might cause troubles later when executed in parallel)
for module_name, module in inspect.getmembers(sys.modules[__name__], inspect.ismodule):
    for _, obj in inspect.getmembers(module, inspect.isclass):

        if not issubclass(obj, JsonSchemaMixin) or obj is JsonSchemaMixin:
            continue

        try:
            obj.from_dict({})
        except ValidationError:
            pass
