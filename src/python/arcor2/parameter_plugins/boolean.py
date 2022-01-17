from ast import NameConstant
from typing import Any

from arcor2.cached import CachedProject as CProject
from arcor2.cached import CachedScene as CScene
from arcor2.parameter_plugins.base import ParameterPlugin, TypesDict
from arcor2.parameter_plugins.list import ListParameterPlugin, get_type_name


class BooleanPlugin(ParameterPlugin):

    COUNTABLE = True

    @classmethod
    def type(cls) -> Any:
        return bool

    @classmethod
    def type_name(cls) -> str:
        return "boolean"

    @classmethod
    def parameter_value(
        cls, type_defs: TypesDict, scene: CScene, project: CProject, action_id: str, parameter_id: str
    ) -> bool:
        return super(BooleanPlugin, cls).parameter_value(type_defs, scene, project, action_id, parameter_id)

    @classmethod
    def _value_from_json(cls, value: str) -> bool:
        return super(BooleanPlugin, cls)._value_from_json(value)

    @classmethod
    def parameter_ast(
        cls, type_defs: TypesDict, scene: CScene, project: CProject, action_id: str, parameter_id: str
    ) -> NameConstant:
        return NameConstant(
            value=cls.parameter_execution_value(type_defs, scene, project, action_id, parameter_id), kind=None
        )


class BooleanListPlugin(ListParameterPlugin):
    @classmethod
    def type(cls):
        return list[bool]

    @classmethod
    def type_name(cls) -> str:
        return get_type_name(BooleanPlugin)

    @classmethod
    def parameter_value(
        cls, type_defs: TypesDict, scene: CScene, project: CProject, action_id: str, parameter_id: str
    ) -> list[bool]:
        return super(BooleanListPlugin, cls).parameter_value(type_defs, scene, project, action_id, parameter_id)
