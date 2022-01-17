import copy
from ast import Attribute, Load, Name
from typing import Any

from arcor2 import json
from arcor2 import transformations as tr
from arcor2.cached import CachedProject as CProject
from arcor2.cached import CachedScene as CScene
from arcor2.data.common import Pose
from arcor2.exceptions import Arcor2Exception
from arcor2.parameter_plugins import ParameterPluginException
from arcor2.parameter_plugins.base import ParameterPlugin, TypesDict
from arcor2.parameter_plugins.list import ListParameterPlugin, get_type_name


class PosePlugin(ParameterPlugin):
    @classmethod
    def type(cls) -> Any:
        return Pose

    @classmethod
    def orientation_id(cls, project: CProject, action_id: str, parameter_id: str) -> str:
        return cls._id_from_value(project.action(action_id).parameter(parameter_id).value)

    @classmethod
    def parameter_value(
        cls, type_defs: TypesDict, scene: CScene, project: CProject, action_id: str, parameter_id: str
    ) -> Pose:

        try:
            ap, ori = project.bare_ap_and_orientation(cls.orientation_id(project, action_id, parameter_id))
        except Arcor2Exception as e:
            raise ParameterPluginException("Failed to get scene/project data.") from e
        return Pose(ap.position, ori.orientation)

    @classmethod
    def parameter_execution_value(
        cls, type_defs: TypesDict, scene: CScene, project: CProject, action_id: str, parameter_id: str
    ) -> Pose:

        # return copy in order to avoid unwanted changes in the original value if an action modifies the parameter
        return copy.deepcopy(
            tr.abs_pose_from_ap_orientation(scene, project, cls.orientation_id(project, action_id, parameter_id))
        )

    @classmethod
    def value_to_json(cls, value: Pose) -> str:
        return value.to_json()

    @classmethod
    def uses_orientation(cls, project: CProject, action_id: str, parameter_id: str, orientation_id: str) -> bool:

        return orientation_id == cls.orientation_id(project, action_id, parameter_id)

    @classmethod
    def parameter_ast(
        cls, type_defs: TypesDict, scene: CScene, project: CProject, action_id: str, parameter_id: str
    ) -> Attribute:

        ori_ap, ori = project.bare_ap_and_orientation(cls.orientation_id(project, action_id, parameter_id))

        return Attribute(
            value=Attribute(
                value=Attribute(
                    value=Name(id="aps", ctx=Load()), attr=ori_ap.name, ctx=Load()  # TODO this should not be hardcoded
                ),
                attr="poses",  # TODO this should not be hardcoded
                ctx=Load(),
            ),
            attr=ori.name,
            ctx=Load(),
        )


class PoseListPlugin(ListParameterPlugin):
    @classmethod
    def type(cls):
        return list[Pose]

    @classmethod
    def type_name(cls) -> str:
        return get_type_name(PosePlugin)

    @classmethod
    def parameter_value(
        cls, type_defs: TypesDict, scene: CScene, project: CProject, action_id: str, parameter_id: str
    ) -> list[Pose]:

        ret: list[Pose] = []

        ap, action = project.action_point_and_action(action_id)
        parameter = action.parameter(parameter_id)

        for orientation_id in cls._param_value_list(parameter):
            ret.append(Pose(ap.position, project.orientation(orientation_id).orientation))

        return ret

    @classmethod
    def parameter_execution_value(
        cls, type_defs: TypesDict, scene: CScene, project: CProject, action_id: str, parameter_id: str
    ) -> list[Pose]:

        ap, action = project.action_point_and_action(action_id)

        if not ap.parent:
            return copy.deepcopy(cls.parameter_value(type_defs, scene, project, action_id, parameter_id))

        parameter = action.parameter(parameter_id)
        ret: list[Pose] = []

        for orientation_id in cls._param_value_list(parameter):
            ret.append(copy.deepcopy(tr.abs_pose_from_ap_orientation(scene, project, orientation_id)))

        return ret

    @classmethod
    def value_to_json(cls, value: list[Pose]) -> str:
        return json.dumps([v.to_json() for v in value])

    @classmethod
    def uses_orientation(cls, project: CProject, action_id: str, parameter_id: str, orientation_id: str) -> bool:

        action = project.action(action_id)
        param = action.parameter(parameter_id)

        for ori_id in cls._param_value_list(param):
            if ori_id == orientation_id:
                return True
        return False
