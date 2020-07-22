import abc
import copy
from dataclasses import dataclass
from typing import List, Optional, Set

from dataclasses_jsonschema import JsonSchemaMixin

from arcor2 import CancelDict, DynamicParamDict
from arcor2.clients import scene_service
from arcor2.data.common import Joint, Pose, SceneObject
from arcor2.data.object_type import Models
from arcor2.docstring import parse_docstring
from arcor2.exceptions import Arcor2Exception


class GenericException(Arcor2Exception):
    pass


class Generic(metaclass=abc.ABCMeta):
    """
    Generic object
    """

    @dataclass
    class Settings(JsonSchemaMixin):
        pass

    DYNAMIC_PARAMS: DynamicParamDict = {}
    CANCEL_MAPPING: CancelDict = {}

    def __init__(self, obj_id: str, name: str, settings: Optional[Settings] = None) -> None:

        self.id = obj_id
        self.name = name

        if settings is None:
            settings = Generic.Settings()

        self.settings: Generic.Settings = settings

    @classmethod
    def description(cls) -> str:
        if not cls.__doc__:
            return "No description available."
        return parse_docstring(cls.__doc__)["short_description"]

    def scene_object(self) -> SceneObject:
        return SceneObject(self.id, self.name, self.__class__.__name__)

    def __repr__(self) -> str:
        return str(self.__dict__)

    def cleanup(self) -> None:
        """
        This method is called when a scene is closed or when script ends.
        :return:
        """
        pass


class GenericWithPose(Generic):

    def __init__(self, obj_id: str, name: str, pose: Pose, collision_model: Optional[Models] = None):

        super(GenericWithPose, self).__init__(obj_id, name)

        self._pose = pose
        self.collision_model = copy.deepcopy(collision_model)
        if self.collision_model:
            # originally, each model has id == object type (e.g. BigBox) but here we need to set it to something unique
            self.collision_model.id = self.id
            scene_service.upsert_collision(self.collision_model, pose)

    def scene_object(self) -> SceneObject:
        return SceneObject(self.id, self.name, self.__class__.__name__, self._pose)

    @property
    def pose(self) -> Pose:
        return self._pose

    @pose.setter
    def pose(self, pose: Pose) -> None:
        self._pose = pose
        if self.collision_model:
            scene_service.upsert_collision(self.collision_model, pose)

    def cleanup(self) -> None:

        super(GenericWithPose, self).cleanup()

        if self.collision_model:
            scene_service.delete_collision_id(self.collision_model.id)


class Robot(GenericWithPose, metaclass=abc.ABCMeta):
    """
    Abstract class representing robot and its basic capabilities (motion)
    """

    urdf_package_path: Optional[str] = None

    @abc.abstractmethod
    def get_end_effectors_ids(self) -> Set[str]:
        pass

    @abc.abstractmethod
    def get_end_effector_pose(self, end_effector: str) -> Pose:
        pass

    @abc.abstractmethod
    def robot_joints(self) -> List[Joint]:
        pass

    @abc.abstractmethod
    def grippers(self) -> Set[str]:
        return set()

    @abc.abstractmethod
    def suctions(self) -> Set[str]:
        return set()

    def move_to_pose(self, end_effector_id: str, target_pose: Pose, speed: float) -> None:
        """
        Move given robot's end effector to the selected pose.
        :param end_effector_id:
        :param target_pose:
        :param speed:
        :return:
        """

        assert .0 <= speed <= 1.
        raise NotImplementedError("Robot does not support moving to pose.")

    def move_to_joints(self, target_joints: List[Joint], speed: float) -> None:
        """
        Sets target joint values.
        :param target_joints:
        :param speed:
        :return:
        """

        assert .0 <= speed <= 1.
        raise NotImplementedError("Robot does not support moving to joints.")

    def stop(self) -> None:
        raise NotImplementedError("The robot can't be stopped.")


__ALL__ = [
    Generic.__name__,
    GenericWithPose.__name__,
    Robot.__name__,
    GenericException.__name__
]
