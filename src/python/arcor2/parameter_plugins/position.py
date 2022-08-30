import copy
from ast import Attribute, Load, Name
from typing import Any

from arcor2 import transformations as tr
from arcor2.cached import CachedProject as CProject
from arcor2.cached import CachedScene as CScene
from arcor2.data.common import Position
from arcor2.exceptions import Arcor2Exception
from arcor2.parameter_plugins import ParameterPluginException
from arcor2.parameter_plugins.base import ParameterPlugin, TypesDict


class PositionPlugin(ParameterPlugin):
    @classmethod
    def type(cls) -> Any:
        return Position

    @classmethod
    def ap_id(cls, project: CProject, action_id: str, parameter_id: str) -> str:
        return cls._id_from_value(project.action(action_id).parameter(parameter_id).value)

    @classmethod
    def parameter_value(
        cls, type_defs: TypesDict, scene: CScene, project: CProject, action_id: str, parameter_id: str
    ) -> Position:

        try:
            ap = project.bare_action_point(cls.ap_id(project, action_id, parameter_id))
        except Arcor2Exception as e:
            raise ParameterPluginException("Failed to get scene/project data.") from e
        return ap.position

    @classmethod
    def parameter_execution_value(
        cls, type_defs: TypesDict, scene: CScene, project: CProject, action_id: str, parameter_id: str
    ) -> Position:

        # return copy in order to avoid unwanted changes in the original value if an action modifies the parameter
        return copy.deepcopy(tr.abs_position_from_ap(scene, project, cls.ap_id(project, action_id, parameter_id)))

    @classmethod
    def value_to_json(cls, value: Position) -> str:
        return value.to_json()

    @classmethod
    def parameter_ast(
        cls, type_defs: TypesDict, scene: CScene, project: CProject, action_id: str, parameter_id: str
    ) -> Attribute:

        ap = project.bare_action_point(cls.ap_id(project, action_id, parameter_id))

        return Attribute(
            value=Attribute(
                value=Name(id="aps", ctx=Load()), attr=ap.name, ctx=Load()  # TODO this should not be hardcoded
            ),
            attr="position",  # TODO this should not be hardcoded
            ctx=Load(),
        )
