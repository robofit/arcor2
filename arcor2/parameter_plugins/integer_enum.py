from typing import get_type_hints, Callable
from enum import Enum

from arcor2.data.common import Project, IntEnum, Scene
from arcor2.data.object_type import ActionParameterMeta
from arcor2.parameter_plugins.base import ParameterPlugin, TypesDict, ParameterPluginException

# TODO move IntEnum definition here?


class IntegerEnumPlugin(ParameterPlugin):

    EXACT_TYPE = False

    @classmethod
    def type(cls):
        return IntEnum

    @classmethod
    def type_name(cls) -> str:
        return "integer_enum"

    @classmethod
    def meta(cls, param_meta: ActionParameterMeta, action_method: Callable, source: str) -> None:
        super(IntegerEnumPlugin, cls).meta(param_meta, action_method, source)

        ttype = get_type_hints(action_method)[param_meta.name]
        if not issubclass(ttype, cls.type()):
            raise ParameterPluginException(f"Type {ttype.__name__} is not subclass of {cls.type().__name__}.")

        param_meta.allowed_values = ttype.set()

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

        return ttype(param.value)
