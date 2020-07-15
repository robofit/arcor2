from typing import Any, List

from arcor2.cached import CachedProject
from arcor2.data.common import Scene
from arcor2.parameter_plugins.base import ParameterPlugin, TypesDict
from arcor2.parameter_plugins.list import ListParameterPlugin, get_type_name


class StringPlugin(ParameterPlugin):

    @classmethod
    def type(cls) -> Any:
        return str

    @classmethod
    def type_name(cls) -> str:
        return "string"

    @classmethod
    def value(cls, type_defs: TypesDict, scene: Scene, project: CachedProject, action_id: str, parameter_id: str) \
            -> str:
        return cls.type()(super(StringPlugin, cls).value(type_defs, scene, project, action_id, parameter_id))


class StringListPlugin(ListParameterPlugin):

    @classmethod
    def type(cls):
        return List[str]

    @classmethod
    def type_name(cls) -> str:
        return get_type_name(StringPlugin)

    @classmethod
    def value(cls, type_defs: TypesDict, scene: Scene, project: CachedProject, action_id: str, parameter_id: str) \
            -> List[str]:
        return super(StringListPlugin, cls).value(type_defs, scene, project, action_id, parameter_id)
