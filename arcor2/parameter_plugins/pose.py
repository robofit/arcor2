from typing import List
import json

from arcor2.data.common import Project, Pose, Scene
from arcor2.parameter_plugins.base import ParameterPlugin, TypesDict
from arcor2.parameter_plugins.list import ListParameterPlugin, get_type_name
from arcor2 import helpers as hlp


class PosePlugin(ParameterPlugin):

    @classmethod
    def type(cls):
        return Pose

    @classmethod
    def value(cls, type_defs: TypesDict, scene: Scene, project: Project, action_id: str, parameter_id: str) -> Pose:

        action = project.action(action_id)
        param = action.parameter(parameter_id)
        ori_id: str = cls.param_value(param)

        ap, ori = project.ap_and_orientation(ori_id)
        return Pose(ap.position, ori.orientation)

    @classmethod
    def execution_value(cls, type_defs: TypesDict, scene: Scene, project: Project, action_id: str,
                        parameter_id: str) -> Pose:

        action = project.action(action_id)
        param = action.parameter(parameter_id)
        ori_id: str = cls.param_value(param)

        ap, ori = project.ap_and_orientation(ori_id)

        if not ap.parent:
            return Pose(ap.position, ori.orientation)

        obj = scene.object(ap.parent)
        p = hlp.make_pose_abs(obj.pose, Pose(ap.position, ori.orientation))
        return p

    @classmethod
    def value_to_json(cls, value: Pose) -> str:
        return value.to_json()

    @classmethod
    def uses_orientation(cls, project: Project, action_id: str, parameter_id: str, orientation_id: str) -> bool:

        action = project.action(action_id)
        param = action.parameter(parameter_id)
        return orientation_id == cls.param_value(param)


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

        ap, action = project.action_point_and_action(action_id)
        parameter = action.parameter(parameter_id)

        for orientation_id in cls.param_value_list(parameter):
            ret.append(Pose(ap.position, ap.orientation(orientation_id).orientation))

        return ret

    @classmethod
    def execution_value(cls, type_defs: TypesDict, scene: Scene, project: Project, action_id: str, parameter_id: str) \
            -> List[Pose]:

        ap, action = project.action_point_and_action(action_id)

        if not ap.parent:
            return cls.value(type_defs, scene, project, action_id, parameter_id)

        parameter = action.parameter(parameter_id)
        ret: List[Pose] = []

        obj = scene.object(ap.parent)

        for orientation_id in cls.param_value_list(parameter):
            ret.append(hlp.make_pose_abs(obj.pose, Pose(ap.position, ap.orientation(orientation_id).orientation)))

        return ret

    @classmethod
    def value_to_json(cls, value: List[Pose]) -> str:
        return json.dumps([v.to_json() for v in value])

    @classmethod
    def uses_orientation(cls, project: Project, action_id: str, parameter_id: str, orientation_id: str) -> bool:

        action = project.action(action_id)
        param = action.parameter(parameter_id)

        for ori_id in cls.param_value_list(param):
            if ori_id == orientation_id:
                return True
        return False
