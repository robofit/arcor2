from arcor2.data.common import Project, RobotJoints, Scene
from arcor2.parameter_plugins.base import ParameterPlugin, TypesDict, ParameterPluginException
from arcor2.services import RobotService


class JointsPlugin(ParameterPlugin):

    @classmethod
    def type(cls):
        return RobotJoints

    @classmethod
    def type_name(cls) -> str:
        return "joints"

    @classmethod
    def value(cls, type_defs: TypesDict, scene: Scene, project: Project, action_id: str, parameter_id: str) -> \
            RobotJoints:

        param = project.action(action_id).parameter(parameter_id)
        robot_id, ap_id, value_id = cls.parse_id(param)

        if issubclass(type_defs[robot_id], RobotService):

            action = project.action(action_id)

            for param in action.parameters:
                if param.id == "robot_id":
                    robot_id = param.value
                    break
            else:
                raise ParameterPluginException(f"Parameter {param.id} of action {action.id} depends on"
                                               f" 'robot_id' parameter, which could not be found.")

        return project.action_point(ap_id).get_joints(robot_id, value_id)
