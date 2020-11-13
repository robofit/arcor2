import json
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Optional, Set, get_type_hints

from dataclasses_jsonschema import JsonSchemaMixin
from typed_ast import ast3 as ast

from arcor2.cached import CachedProject as CProject
from arcor2.cached import CachedScene as CScene
from arcor2.data.common import IntEnum
from arcor2.data.object_type import ParameterMeta
from arcor2.parameter_plugins.base import ParameterPlugin, ParameterPluginException, TypesDict

# TODO move IntEnum definition here?


@dataclass
class IntegerEnumExtra(JsonSchemaMixin):

    allowed_values: Optional[Set[Any]] = None


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
        except ValueError:
            raise ParameterPluginException(f"Parameter {parameter_id} of action {action.name} has invalid value.")
