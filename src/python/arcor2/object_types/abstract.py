import abc
import copy
import inspect
from dataclasses import dataclass
from typing import List, Optional, Set

from dataclasses_jsonschema import JsonSchemaMixin
from PIL import Image

from arcor2 import CancelDict, DynamicParamDict
from arcor2.clients import scene_service
from arcor2.data.camera import CameraParameters
from arcor2.data.common import Joint, Pose, SceneObject
from arcor2.data.object_type import Models
from arcor2.data.robot import RobotType
from arcor2.docstring import parse_docstring
from arcor2.exceptions import Arcor2Exception, Arcor2NotImplemented
from arcor2.helpers import NonBlockingLock


class GenericException(Arcor2Exception):
    pass


@dataclass
class Settings(JsonSchemaMixin):
    """Default (empty) settings for ARCOR2 objects."""

    pass


class Generic(metaclass=abc.ABCMeta):
    """Generic object."""

    DYNAMIC_PARAMS: DynamicParamDict = {}
    CANCEL_MAPPING: CancelDict = {}
    _ABSTRACT = True

    def __init__(self, obj_id: str, name: str, settings: Optional[Settings] = None) -> None:

        self.id = obj_id
        self.name = name

        if settings is None:
            settings = Settings()
        self._settings = settings

    @classmethod
    def abstract(cls) -> bool:
        return inspect.isabstract(cls) or cls._ABSTRACT

    @property
    def settings(self) -> Settings:
        return self._settings

    @classmethod
    def description(cls) -> str:
        if not cls.__doc__:
            return "No description available."
        return parse_docstring(cls.__doc__)["short_description"]

    def scene_object(self) -> SceneObject:
        return SceneObject(self.name, self.__class__.__name__, id=self.id)

    def __repr__(self) -> str:
        return str(self.__dict__)

    def cleanup(self) -> None:
        """This method is called when a scene is closed or when script ends.

        :return:
        """
        pass


class GenericWithPose(Generic):
    def __init__(
        self,
        obj_id: str,
        name: str,
        pose: Pose,
        collision_model: Optional[Models] = None,
        settings: Optional[Settings] = None,
    ) -> None:

        super(GenericWithPose, self).__init__(obj_id, name, settings)

        self._pose = pose
        self.collision_model = copy.deepcopy(collision_model)
        if self.collision_model:
            # originally, each model has id == object type (e.g. BigBox) but here we need to set it to something unique
            self.collision_model.id = self.id
            scene_service.upsert_collision(self.collision_model, pose)

    def scene_object(self) -> SceneObject:
        return SceneObject(self.name, self.__class__.__name__, self._pose, id=self.id)

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


class RobotException(Arcor2Exception):
    pass


class Robot(GenericWithPose, metaclass=abc.ABCMeta):
    """Abstract class representing robot and its basic capabilities (motion)"""

    def __init__(self, obj_id: str, name: str, pose: Pose, settings: Optional[Settings] = None) -> None:
        super(Robot, self).__init__(obj_id, name, pose, None, settings)
        self._move_lock = NonBlockingLock()

    robot_type = RobotType.ARTICULATED
    urdf_package_name: Optional[str] = None

    @property
    def move_in_progress(self) -> bool:
        return self._move_lock.locked()

    def check_if_ready_to_move(self) -> None:
        """The method should raise exception when the robot is not ready to
        move for some reason.

        :return:
        """

        if self.move_in_progress:
            raise RobotException("Already moving.")

        try:
            if self.get_hand_teaching_mode():
                raise RobotException("Can't move in hand teaching mode.")
        except Arcor2NotImplemented:
            pass

        return None

    def move_to_calibration_pose(self) -> None:
        raise Arcor2NotImplemented("No calibration pose specified.")

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

    def move_to_pose(self, end_effector_id: str, target_pose: Pose, speed: float, safe: bool = True) -> None:
        """Move given robot's end effector to the selected pose.

        :param end_effector_id:
        :param target_pose:
        :param speed:
        :param safe:
        :return:
        """

        assert 0.0 <= speed <= 1.0
        raise Arcor2NotImplemented("Robot does not support moving to pose.")

    def move_to_joints(self, target_joints: List[Joint], speed: float, safe: bool = True) -> None:
        """Sets target joint values.

        :param target_joints:
        :param speed:
        :param safe:
        :return:
        """

        assert 0.0 <= speed <= 1.0
        raise Arcor2NotImplemented("Robot does not support moving to joints.")

    def stop(self) -> None:
        raise Arcor2NotImplemented("The robot can't be stopped.")

    def inverse_kinematics(
        self,
        end_effector_id: str,
        pose: Pose,
        start_joints: Optional[List[Joint]] = None,
        avoid_collisions: bool = True,
    ) -> List[Joint]:
        """Computes inverse kinematics.

        :param end_effector_id: IK target pose end-effector
        :param pose: IK target pose
        :param start_joints: IK start joints
        :param avoid_collisions: Return non-collision IK result if true
        :return: Inverse kinematics
        """
        raise Arcor2NotImplemented()

    def forward_kinematics(self, end_effector_id: str, joints: List[Joint]) -> Pose:
        """Computes forward kinematics.

        :param end_effector_id: Target end effector name
        :param joints: Input joint values
        :return: Pose of the given end effector
        """
        raise Arcor2NotImplemented()

    def get_hand_teaching_mode(self) -> bool:
        """
        This is expected to be implemented if the robot supports set_hand_teaching_mode
        :return:
        """
        raise Arcor2NotImplemented()

    def set_hand_teaching_mode(self, enabled: bool) -> None:
        raise Arcor2NotImplemented()


class Camera(GenericWithPose, metaclass=abc.ABCMeta):
    """Abstract class representing camera and its basic capabilities."""

    def __init__(
        self,
        obj_id: str,
        name: str,
        pose: Pose,
        collision_model: Optional[Models] = None,
        settings: Optional[Settings] = None,
    ) -> None:
        super(Camera, self).__init__(obj_id, name, pose, collision_model, settings)

        self.color_camera_params: Optional[CameraParameters] = None

    def color_image(self, *, an: Optional[str] = None) -> Image.Image:
        raise Arcor2NotImplemented()

    def depth_image(self, averaged_frames: int = 1, *, an: Optional[str] = None) -> Image.Image:
        """This should provide depth image transformed into color camera
        perspective.

        :return:
        """

        raise Arcor2NotImplemented()


__all__ = [
    Generic.__name__,
    GenericWithPose.__name__,
    Robot.__name__,
    GenericException.__name__,
    RobotException.__name__,
    Camera.__name__,
]
