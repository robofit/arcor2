from typing import Any, List

from arcor2.cached import CachedProject as CProject, CachedScene as CScene
from arcor2.parameter_plugins.base import ParameterPlugin, TypesDict
from arcor2.parameter_plugins.list import ListParameterPlugin, get_type_name


class BooleanPlugin(ParameterPlugin):

    @classmethod
    def type(cls) -> Any:
        return bool

    @classmethod
    def type_name(cls) -> str:
        return "boolean"

    @classmethod
    def value(cls, type_defs: TypesDict, scene: CScene, project: CProject, action_id: str, parameter_id: str) \
            -> bool:
        return cls.type()(super(BooleanPlugin, cls).value(type_defs, scene, project, action_id, parameter_id))


class BooleanListPlugin(ListParameterPlugin):

    @classmethod
    def type(cls):
        return List[bool]

    @classmethod
    def type_name(cls) -> str:
        return get_type_name(BooleanPlugin)

    @classmethod
    def value(cls, type_defs: TypesDict, scene: CScene, project: CProject, action_id: str, parameter_id: str) \
            -> List[bool]:
        return super(BooleanListPlugin, cls).value(type_defs, scene, project, action_id, parameter_id)
