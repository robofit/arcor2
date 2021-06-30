import ast
import inspect
import os
import shutil
from dataclasses import is_dataclass
from typing import Any, Callable, Dict, Iterator, List, Optional, Set, Tuple, Type, Union, get_type_hints

import typing_inspect
from dataclasses_jsonschema import JsonSchemaMixin, ValidationError

import arcor2
from arcor2 import json
from arcor2.data.common import ActionMetadata, Parameter
from arcor2.exceptions import Arcor2Exception
from arcor2.object_types.abstract import Generic, Settings
from arcor2.source.utils import find_class_def, parse


class ObjectTypeException(Arcor2Exception):
    pass


def get_containing_module_sources(type_def: Type[object]) -> str:
    """Returns sources of the whole containing module.

    ...whereas inspect.getsource(type_def) returns just source of the class itself
    :param type_def:
    :return:
    """

    with open(inspect.getfile(type_def), "r") as source_file:
        return source_file.read()


def check_object_type(type_def: Type[Generic]) -> None:
    """Checks whether the object type source is a valid one.

    :param type_def:
    :return:
    """

    if not issubclass(type_def, Generic):
        raise ObjectTypeException("Not a subclass of Generic.")

    # it might happen that the code is ok, but can't be parsed e.g. due to unsupported placement of comment
    # parse_def is not enough here - there might be something unparseable outside of the ObjectType class itself
    parse(get_containing_module_sources(type_def))

    # TODO some more (simple) checks here?


def built_in_types() -> Iterator[Tuple[str, Type[Generic]]]:
    """Yields class name and class definition tuple."""

    for cls_name, cls_type in inspect.getmembers(arcor2.object_types.abstract, inspect.isclass):
        if not issubclass(cls_type, Generic):
            continue

        yield cls_name, cls_type


def get_built_in_type(name: str) -> Type[Generic]:

    for bname, cls in built_in_types():
        if name == bname:
            return cls

    raise KeyError


def built_in_types_names() -> Set[str]:
    return {type_name for type_name, _ in built_in_types()}


class DataError(Arcor2Exception):
    pass


# TODO settings_to_params


def settings_from_params(
    type_def: Type[Generic], settings: List[Parameter], overrides: Optional[List[Parameter]] = None
) -> Settings:
    """Constructs instance of Settings from two arrays of parameters (scene
    settings and project overrides).

    :param type_def:
    :param settings:
    :param overrides:
    :return:
    """

    if overrides is None:
        overrides = []

    final: Dict[str, Parameter] = {s.name: s for s in settings}
    for over in overrides:
        if over.name not in final:
            raise Arcor2Exception("Invalid override.")

        if over.type != final[over.name].type:
            raise Arcor2Exception("Type mismatch.")

        final[over.name] = over

    settings_def = get_settings_def(type_def)
    settings_data: Dict[str, Any] = {}

    settings_def_type_hints = get_type_hints(settings_def.__init__)

    for s in final.values():

        try:
            setting_def = settings_def_type_hints[s.name]
        except KeyError as e:
            raise Arcor2Exception(f"Unknown property {s.name}.") from e

        try:
            if issubclass(setting_def, JsonSchemaMixin):
                settings_data[s.name] = json.loads(s.value)
            else:
                settings_data[s.name] = setting_def(json.loads(s.value))
        except (json.JsonException, ValidationError) as e:
            raise Arcor2Exception(f"Parameter {s.name} has invalid value.") from e

    try:
        settings_cls = settings_def.from_dict(settings_data)
    except (ValueError, ValidationError) as e:
        raise Arcor2Exception("Validation of settings failed.") from e

    return settings_cls


def get_settings_def(type_def: Type[Generic]) -> Type[Settings]:
    """Get settings definition from object type definition.

    :param type_def:
    :return:
    """

    sig = inspect.signature(type_def.__init__)
    try:
        param = sig.parameters["settings"]
    except KeyError:
        raise Arcor2Exception("Type has no settings.")

    if typing_inspect.is_optional_type(param.annotation):
        settings_cls = typing_inspect.get_args(param.annotation)[0]
    else:
        settings_cls = param.annotation

    try:
        if not issubclass(settings_cls, Settings):
            raise Arcor2Exception("Settings have invalid type.")
    except TypeError:
        raise Arcor2Exception("Settings have invalid annotation.")

    if not is_dataclass(settings_cls):
        raise Arcor2Exception("Settings misses @dataclass decorator.")

    return settings_cls


def base_from_source(source: Union[str, ast.AST], cls_name: str) -> List[str]:
    """Returns list, where the first element is name of the base class and
    others are mixins.

    :param source:
    :param cls_name:
    :return:
    """

    if isinstance(source, str):
        cls_def = find_class_def(cls_name, parse(source))
    else:
        cls_def = find_class_def(cls_name, source)

    if not cls_def.bases:
        return []

    ret: List[str] = []

    for base in reversed(cls_def.bases):

        assert isinstance(base, ast.Name)
        ret.append(base.id)

    return ret


def iterate_over_actions(
    type_def: Type[Generic],
) -> Iterator[Tuple[str, Callable[[Any,], Any]]]:

    for method_name, method in inspect.getmembers(type_def, inspect.isroutine):

        try:
            if not isinstance(method.__action__, ActionMetadata):
                continue
        except AttributeError:
            continue

        yield method_name, method


def prepare_object_types_dir(path: str, module: str) -> None:
    """Creates a fresh directory, where ObjectTypes will be placed.

    :param path:
    :param module:
    :return:
    """

    full_path = os.path.join(path, module)

    if os.path.exists(full_path):
        shutil.rmtree(full_path)

    os.makedirs(full_path)

    with open(os.path.join(full_path, "__init__.py"), "w"):
        pass


__all__ = [
    ObjectTypeException.__name__,
    built_in_types.__name__,
    get_built_in_type.__name__,
    built_in_types_names.__name__,
    DataError.__name__,
]
