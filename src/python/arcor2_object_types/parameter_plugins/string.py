from ast import Constant
from typing import Any

from arcor2.cached import CachedProject as CProject
from arcor2.cached import CachedScene as CScene
from arcor2_object_types.parameter_plugins.base import ParameterPlugin, TypesDict
from arcor2_object_types.parameter_plugins.list import ListParameterPlugin, get_type_name


class StringPlugin(ParameterPlugin):
    @classmethod
    def type(cls) -> Any:
        return str

    @classmethod
    def type_name(cls) -> str:
        return "string"

    @classmethod
    def parameter_value(
        cls, type_defs: TypesDict, scene: CScene, project: CProject, action_id: str, parameter_id: str
    ) -> str:
        return super(StringPlugin, cls).parameter_value(type_defs, scene, project, action_id, parameter_id)

    @classmethod
    def parameter_ast(
        cls, type_defs: TypesDict, scene: CScene, project: CProject, action_id: str, parameter_id: str
    ) -> Constant:
        return Constant(value=cls.parameter_execution_value(type_defs, scene, project, action_id, parameter_id))


class StringListPlugin(ListParameterPlugin):
    @classmethod
    def type(cls):
        return list[str]

    @classmethod
    def type_name(cls) -> str:
        return get_type_name(StringPlugin)

    @classmethod
    def parameter_value(
        cls, type_defs: TypesDict, scene: CScene, project: CProject, action_id: str, parameter_id: str
    ) -> list[str]:
        return super(StringListPlugin, cls).parameter_value(type_defs, scene, project, action_id, parameter_id)
