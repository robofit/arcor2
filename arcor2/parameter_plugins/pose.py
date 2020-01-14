from arcor2.data.common import Project, Pose, Scene
from arcor2.parameter_plugins.base import ParameterPlugin, TypesDict


class PosePlugin(ParameterPlugin):

    @classmethod
    def type(cls):
        return Pose

    @classmethod
    def value(cls, type_defs: TypesDict, scene: Scene, project: Project, action_id: str, parameter_id: str) -> Pose:

        obj_id, ap_id, value_id = cls.parse_id(project.action(action_id).parameter(parameter_id))
        return project.action_point(ap_id).pose(value_id)
