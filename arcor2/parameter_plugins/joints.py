import json

from arcor2.data.common import Project, ProjectRobotJoints, Scene
from arcor2.parameter_plugins.base import ParameterPlugin, TypesDict, ParameterPluginException
from arcor2.services import RobotService


class JointsPlugin(ParameterPlugin):

    @classmethod
    def type(cls):
        return ProjectRobotJoints

    @classmethod
    def type_name(cls) -> str:
        return "joints"

    @classmethod
    def value(cls, type_defs: TypesDict, scene: Scene, project: Project, action_id: str, parameter_id: str) -> \
            ProjectRobotJoints:

        param = project.action(action_id).parameter(parameter_id)
        _, ap_id, value_id = cls.parse_id(param)

        action = project.action(action_id)
        robot_id, action_method_name = action.parse_type()
        robot_type = scene.object_or_service(robot_id)

        if issubclass(type_defs[robot_type.type], RobotService):

            for param in action.parameters:
                if param.id == "robot_id":
                    robot_id = json.loads(param.value)
                    break
            else:
                raise ParameterPluginException(f"Parameter {param.id} of action {action.id} depends on"
                                               f" 'robot_id' parameter, which could not be found.")

        return project.action_point(ap_id).get_joints(robot_id, value_id)

    @classmethod
    def value_to_json(cls, value: ProjectRobotJoints) -> str:
        return value.to_json()
