import ast
import inspect
from ast import Attribute, Load, Name
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Optional, get_type_hints

from dataclasses_jsonschema import JsonSchemaMixin

from arcor2 import json
from arcor2.cached import CachedProject as CProject
from arcor2.cached import CachedScene as CScene
from arcor2.data.common import IntEnum
from arcor2.data.object_type import ParameterMeta
from arcor2.parameter_plugins.base import ImportTuple, ParameterPlugin, ParameterPluginException, TypesDict

# TODO move IntEnum definition here?


@dataclass
class IntegerEnumExtra(JsonSchemaMixin):

    allowed_values: Optional[set[Any]] = None


class IntegerEnumPlugin(ParameterPlugin):

    EXACT_TYPE = False
    COUNTABLE = True

    @classmethod
    def type(cls) -> Any:
        return IntEnum

    @classmethod
    def type_name(cls) -> str:
        return "integer_enum"

    @classmethod
    def meta(cls, param_meta: ParameterMeta, action_method: Callable, action_node: ast.FunctionDef) -> None:
        super(IntegerEnumPlugin, cls).meta(param_meta, action_method, action_node)

        ttype = get_type_hints(action_method)[param_meta.name]
        if not issubclass(ttype, cls.type()):
            raise ParameterPluginException(f"Type {ttype.__name__} is not subclass of {cls.type().__name__}.")

        param_meta.extra = IntegerEnumExtra(ttype.set()).to_json()

    @classmethod
    def parameter_value(
        cls, type_defs: TypesDict, scene: CScene, project: CProject, action_id: str, parameter_id: str
    ) -> Enum:

        action = project.action(action_id)
        param = action.parameter(parameter_id)
        obj_id, action_type = action.parse_type()
        obj_type_name = scene.object(obj_id).type
        try:
            obj_type = type_defs[obj_type_name]
        except KeyError:
            raise ParameterPluginException(f"Unknown object type {obj_type_name}.")

        try:
            method = getattr(obj_type, action_type)
        except AttributeError:
            raise ParameterPluginException(f"Object type {obj_type_name} does not have method {action_type}.")

        try:
            ttype = get_type_hints(method)[param.name]
        except KeyError:
            raise ParameterPluginException(f"Method {obj_type}/{method.__name__} does not have parameter {param.name}.")

        if not issubclass(ttype, cls.type()):
            raise ParameterPluginException(f"Type {ttype.__name__} is not subclass of {cls.type().__name__}.")

        try:
            return ttype(json.loads(param.value))
        except (ValueError, json.JsonException):
            raise ParameterPluginException(f"Parameter {parameter_id} of action {action.name} has invalid value.")

    @classmethod
    def parameter_ast(
        cls, type_defs: TypesDict, scene: CScene, project: CProject, action_id: str, parameter_id: str
    ) -> Attribute:

        val = cls.parameter_value(type_defs, scene, project, action_id, parameter_id)

        return Attribute(value=Name(id=val.__class__.__name__, ctx=Load()), attr=val.name, ctx=Load())

    @classmethod
    def need_to_be_imported(
        cls, type_defs: TypesDict, scene: CScene, project: CProject, action_id: str, parameter_id: str
    ) -> None | list[ImportTuple]:

        enum_cls = cls.parameter_value(type_defs, scene, project, action_id, parameter_id).__class__
        # TODO does this work as expected in all cases?
        module = inspect.getmodule(enum_cls)
        if not module:
            raise ParameterPluginException("Failed to get the module.")

        # TODO enums are typically defined in the same module as a object type but could be def. elsewhere (arcor2.data)
        return [ImportTuple(f"object_types.{module.__name__.split('.')[-1]}", enum_cls.__name__)]
