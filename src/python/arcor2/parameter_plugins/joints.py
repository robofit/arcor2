from typing import Any

from arcor2.cached import CachedProject as CProject
from arcor2.cached import CachedScene as CScene
from arcor2.data.common import ProjectRobotJoints
from arcor2.exceptions import Arcor2Exception
from arcor2.parameter_plugins.base import ParameterPlugin, ParameterPluginException, TypesDict


class JointsPlugin(ParameterPlugin):
    @classmethod
    def type(cls) -> Any:
        return ProjectRobotJoints

    @classmethod
    def type_name(cls) -> str:
        return "joints"

    @classmethod
    def parameter_value(
        cls, type_defs: TypesDict, scene: CScene, project: CProject, action_id: str, parameter_id: str
    ) -> ProjectRobotJoints:

        try:
            ap, action = project.action_point_and_action(action_id)
            param = action.parameter(parameter_id)
            joints_id = cls._id_from_value(param.value)

            robot_id, action_method_name = action.parse_type()

            joints = project.joints(joints_id)
        except Arcor2Exception as e:
            raise ParameterPluginException("Failed to get necessary data from project.") from e

        if joints.robot_id != robot_id:
            raise ParameterPluginException("Joints are for different robot.")

        return joints

    @classmethod
    def value_to_json(cls, value: ProjectRobotJoints) -> str:
        return value.to_json()

    @classmethod
    def uses_robot_joints(cls, project: CProject, action_id: str, parameter_id: str, robot_joints_id: str) -> bool:

        value_id = cls._id_from_value(project.action(action_id).parameter(parameter_id).value)

        return value_id == robot_joints_id
