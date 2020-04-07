from typing import get_type_hints, Callable, Optional, Set, Any
from enum import Enum
import json
from dataclasses import dataclass

from typed_ast import ast3 as ast
from dataclasses_jsonschema import JsonSchemaMixin

from arcor2.data.common import Project, IntEnum, Scene
from arcor2.data.object_type import ActionParameterMeta
from arcor2.parameter_plugins.base import ParameterPlugin, TypesDict, ParameterPluginException

# TODO move IntEnum definition here?


@dataclass
class IntegerEnumExtra(JsonSchemaMixin):

    allowed_values: Optional[Set[Any]] = None


class IntegerEnumPlugin(ParameterPlugin):

    EXACT_TYPE = False

    @classmethod
    def type(cls):
        return IntEnum

    @classmethod
    def type_name(cls) -> str:
        return "integer_enum"

    @classmethod
    def meta(cls, param_meta: ActionParameterMeta, action_method: Callable, action_node: ast.FunctionDef) -> None:
        super(IntegerEnumPlugin, cls).meta(param_meta, action_method, action_node)

        ttype = get_type_hints(action_method)[param_meta.name]
        if not issubclass(ttype, cls.type()):
            raise ParameterPluginException(f"Type {ttype.__name__} is not subclass of {cls.type().__name__}.")

        param_meta.extra = IntegerEnumExtra(ttype.set()).to_json()

    @classmethod
    def value(cls, type_defs: TypesDict, scene: Scene, project: Project, action_id: str, parameter_id: str) -> Enum:

        action = project.action(action_id)
        param = action.parameter(parameter_id)
        obj_id, action_type = action.parse_type()
        obj_type = type_defs[scene.object_or_service(obj_id).type]

        method = getattr(obj_type, action_type)
        ttype = get_type_hints(method)[param.id]

        if not issubclass(ttype, cls.type()):
            raise ParameterPluginException(f"Type {ttype.__name__} is not subclass of {cls.type().__name__}.")

        try:
            return ttype(json.loads(param.value))
        except ValueError:
            raise ParameterPluginException(f"Parameter {parameter_id} of action {action.name} has invalid value.")
