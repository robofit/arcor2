from typing import List
import json

from arcor2.data.common import Project, Pose, Scene
from arcor2.parameter_plugins.base import ParameterPlugin, TypesDict
from arcor2.parameter_plugins.list import ListParameterPlugin, get_type_name


class PosePlugin(ParameterPlugin):

    @classmethod
    def type(cls):
        return Pose

    @classmethod
    def value(cls, type_defs: TypesDict, scene: Scene, project: Project, action_id: str, parameter_id: str) -> Pose:

        obj_id, ap_id, value_id = cls.parse_id(project.action(action_id).parameter(parameter_id))
        return project.action_point(ap_id).pose(value_id)

    @classmethod
    def value_to_json(cls, value: Pose) -> str:
        return value.to_json()


class PoseListPlugin(ListParameterPlugin):

    @classmethod
    def type(cls):
        return List[Pose]

    @classmethod
    def type_name(cls) -> str:
        return get_type_name(PosePlugin)

    @classmethod
    def value(cls, type_defs: TypesDict, scene: Scene, project: Project, action_id: str, parameter_id: str) \
            -> List[Pose]:

        ret: List[Pose] = []

        for obj_id, ap_id, value_id in cls.parse_list_id(project.action(action_id).parameter(parameter_id)):
            ret.append(project.action_point(ap_id).pose(value_id))

        return ret

    @classmethod
    def value_to_json(cls, value: List[Pose]) -> str:
        return json.dumps([v.to_json() for v in value])
