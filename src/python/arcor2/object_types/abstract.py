import abc
import copy
import inspect
from dataclasses import dataclass

from dataclasses_jsonschema import JsonSchemaMixin
from PIL import Image

from arcor2 import CancelDict, DynamicParamDict
from arcor2.clients import scene_service
from arcor2.data.camera import CameraParameters
from arcor2.data.common import ActionMetadata, Joint, Pose, SceneObject
from arcor2.data.object_type import Models, PrimitiveModels
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

    def __init__(self, obj_id: str, name: str, settings: None | Settings = None) -> None:

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
        """Returns short description from docstring comment."""

        docs = parse_docstring(cls.__doc__)

        if not docs.short_description:
            return "No description available."
        return docs.short_description

    def scene_object(self) -> SceneObject:
        return SceneObject(self.name, self.__class__.__name__, id=self.id)

    def __repr__(self) -> str:
        return str(self.__dict__)

    def cleanup(self) -> None:  # noqa:B027
        """This method is called when a scene is closed or when script ends.

        It may or may not be overridden in derived classes (it is not abstract by purpose).

        :return:
        """
        pass


class GenericWithPose(Generic):
    def __init__(
        self,
        obj_id: str,
        name: str,
        pose: Pose,
        settings: None | Settings = None,
    ) -> None:

        super(GenericWithPose, self).__init__(obj_id, name, settings)
        self._pose = pose

    def scene_object(self) -> SceneObject:
        return SceneObject(self.name, self.__class__.__name__, self._pose, id=self.id)

    @property
    def pose(self) -> Pose:
        """Returns pose of the object.

        When set, pose of the collision model is updated on the Scene service.
        :return:
        """
        return self._pose

    @pose.setter
    def pose(self, pose: Pose) -> None:
        self._pose = pose

    def update_pose(self, new_pose: Pose, *, an: None | str = None) -> None:
        """Enables control over object's pose in the world.

        :param new_pose: New pose for the object.
        :return:
        """

        self.pose = new_pose

    update_pose.__action__ = ActionMetadata()  # type: ignore


class CollisionObject(GenericWithPose):

    # name of the file that should be uploaded to the Project service together with this ObjectType
    mesh_filename: None | str = None

    def __init__(
        self,
        obj_id: str,
        name: str,
        pose: Pose,
        collision_model: Models,
        settings: None | Settings = None,
    ) -> None:

        super().__init__(obj_id, name, pose, settings)

        self.collision_model = copy.deepcopy(collision_model)
        self._enabled = True

        # originally, each model has id == object type (e.g. BigBox) but here we need to set it to something unique
        self.collision_model.id = self.id
        scene_service.upsert_collision(self.collision_model, pose)

    @property  # workaround for https://github.com/python/mypy/issues/5936
    def pose(self) -> Pose:
        return super().pose

    @pose.setter
    def pose(self, pose: Pose) -> None:
        self._pose = pose  # TODO how to set it through super() correctly?
        if self._enabled:
            scene_service.upsert_collision(self.collision_model, pose)

    @property
    def enabled(self) -> bool:
        """If the object has a collision model, this indicates whether the
        model is enabled (set on the Scene service).

        When set, it updates the state of the model on the Scene service.
        :return:
        """

        assert self.id in scene_service.collision_ids() == self._enabled
        return self._enabled

    @enabled.setter
    def enabled(self, enabled: bool) -> None:

        if not self._enabled and enabled:
            assert self.id not in scene_service.collision_ids()
            scene_service.upsert_collision(self.collision_model, self.pose)
        if self._enabled and not enabled:
            scene_service.delete_collision_id(self.id)
        self._enabled = enabled

    def set_enabled(self, state: bool, *, an: None | str = None) -> None:
        """Enables control of the object's collision model.

        :param state: State of a collision model.
        :return:
        """
        self.enabled = state

    set_enabled.__action__ = ActionMetadata()  # type: ignore


class VirtualCollisionObject(CollisionObject):
    """Should be used to represent obstacles or another 'dumb' objects at the
    workplace."""

    def __init__(
        self,
        obj_id: str,
        name: str,
        pose: Pose,
        collision_model: PrimitiveModels,
        settings: None | Settings = None,
    ) -> None:

        if settings and not isinstance(settings, Settings):
            # TODO rather remove settings from __init__ (requires non-trivial changes in ARServer/Resources)
            raise Arcor2Exception(f"Settings are not supported for {VirtualCollisionObject.__name__}.")  # noqa:PB10

        super().__init__(obj_id, name, pose, collision_model)


class RobotException(Arcor2Exception):
    pass


class Robot(GenericWithPose, metaclass=abc.ABCMeta):
    """Abstract class representing robot and its basic capabilities (motion)"""

    class KinematicsException(Arcor2Exception):
        pass

    def __init__(self, obj_id: str, name: str, pose: Pose, settings: None | Settings = None) -> None:
        super(Robot, self).__init__(obj_id, name, pose, settings)
        self._move_lock = NonBlockingLock()

    robot_type = RobotType.ARTICULATED
    urdf_package_name: None | str = None

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

    def move_to_calibration_pose(self) -> None:
        raise Arcor2NotImplemented("No calibration pose specified.")

    @abc.abstractmethod
    def get_end_effectors_ids(self) -> set[str]:
        pass

    @abc.abstractmethod
    def get_end_effector_pose(self, end_effector: str) -> Pose:
        pass

    @abc.abstractmethod
    def robot_joints(self, include_gripper: bool = False) -> list[Joint]:
        """Get list of robot's joints.

        :param include_gripper: Whether gripper joints should be added (e.g. for visualization).
        :return:
        """
        pass

    @abc.abstractmethod
    def grippers(self) -> set[str]:
        return set()

    @abc.abstractmethod
    def suctions(self) -> set[str]:
        return set()

    def move_to_pose(
        self, end_effector_id: str, target_pose: Pose, speed: float, safe: bool = True, linear: bool = True
    ) -> None:
        """Move given robot's end effector to the selected pose.

        :param end_effector_id:
        :param target_pose:
        :param speed:
        :param safe:
        :return:
        """

        assert 0.0 <= speed <= 1.0
        raise Arcor2NotImplemented("Robot does not support moving to pose.")

    def move_to_joints(self, target_joints: list[Joint], speed: float, safe: bool = True) -> None:
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
        start_joints: None | list[Joint] = None,
        avoid_collisions: bool = True,
    ) -> list[Joint]:
        """Computes inverse kinematics.

        Should raise KinematicsException when unable to compute.

        :param end_effector_id: IK target pose end-effector
        :param pose: IK target pose
        :param start_joints: IK start joints
        :param avoid_collisions: Return non-collision IK result if true
        :return: Inverse kinematics
        """
        raise Arcor2NotImplemented()

    def forward_kinematics(self, end_effector_id: str, joints: list[Joint]) -> Pose:
        """Computes forward kinematics.

        Should raise KinematicsException when unable to compute.

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
        raise Arcor2NotImplemented("The robot does not support hand teaching.")


class MultiArmRobot(Robot, metaclass=abc.ABCMeta):
    """Abstract class representing robot and its basic capabilities (motion)"""

    @abc.abstractmethod
    def get_arm_ids(self) -> set[str]:
        """Most robots have just one arm so this method is not abstract and
        returns one arm id.

        :return:
        """
        pass

    @abc.abstractmethod
    def get_end_effectors_ids(self, arm_id: None | str = None) -> set[str]:
        pass

    @abc.abstractmethod
    def get_end_effector_pose(self, end_effector: str, arm_id: None | str = None) -> Pose:
        pass

    @abc.abstractmethod
    def robot_joints(self, include_gripper: bool = False, arm_id: None | str = None) -> list[Joint]:
        """With no arm specified, returns all robot joints. Otherwise, returns
        joints for the given arm.

        :param arm_id:
        :return:
        """
        pass

    @abc.abstractmethod
    def grippers(self, arm_id: None | str = None) -> set[str]:
        return set()

    @abc.abstractmethod
    def suctions(self, arm_id: None | str = None) -> set[str]:
        return set()

    def check_if_ready_to_move(self) -> None:
        """The method should raise exception when the robot is not ready to
        move for some reason.

        :return:
        """

        if self.move_in_progress:  # this holds for all arms
            raise RobotException("Already moving.")

        # hand-teaching mode is arm specific
        for arm_id in self.get_arm_ids():

            try:
                if self.get_hand_teaching_mode(arm_id):
                    raise RobotException("Can't move in hand teaching mode.")
            except Arcor2NotImplemented:
                pass

    def move_to_pose(
        self,
        end_effector_id: str,
        target_pose: Pose,
        speed: float,
        safe: bool = True,
        linear: bool = True,
        arm_id: None | str = None,
    ) -> None:
        """Move given robot's end effector to the selected pose.

        :param end_effector_id:
        :param target_pose:
        :param speed:
        :param safe:
        :return:
        """

        assert 0.0 <= speed <= 1.0
        raise Arcor2NotImplemented("Robot does not support moving to pose.")

    def move_to_joints(
        self, target_joints: list[Joint], speed: float, safe: bool = True, arm_id: None | str = None
    ) -> None:
        """Sets target joint values.

        :param target_joints:
        :param speed:
        :param safe:
        :return:
        """

        assert 0.0 <= speed <= 1.0
        raise Arcor2NotImplemented("Robot does not support moving to joints.")

    def inverse_kinematics(
        self,
        end_effector_id: str,
        pose: Pose,
        start_joints: None | list[Joint] = None,
        avoid_collisions: bool = True,
        arm_id: None | str = None,
    ) -> list[Joint]:
        """Computes inverse kinematics.

        :param end_effector_id: IK target pose end-effector
        :param pose: IK target pose
        :param start_joints: IK start joints
        :param avoid_collisions: Return non-collision IK result if true
        :return: Inverse kinematics
        """
        raise Arcor2NotImplemented()

    def forward_kinematics(self, end_effector_id: str, joints: list[Joint], arm_id: None | str = None) -> Pose:
        """Computes forward kinematics.

        :param end_effector_id: Target end effector name
        :param joints: Input joint values
        :return: Pose of the given end effector
        """
        raise Arcor2NotImplemented()

    def get_hand_teaching_mode(self, arm_id: None | str = None) -> bool:
        """
        This is expected to be implemented if the robot supports set_hand_teaching_mode
        :return:
        """
        raise Arcor2NotImplemented()

    def set_hand_teaching_mode(self, enabled: bool, arm_id: None | str = None) -> None:
        raise Arcor2NotImplemented()


class Camera(CollisionObject, metaclass=abc.ABCMeta):
    """Abstract class representing camera and its basic capabilities."""

    def __init__(
        self,
        obj_id: str,
        name: str,
        pose: Pose,
        collision_model: Models,
        settings: None | Settings = None,
    ) -> None:
        super(Camera, self).__init__(obj_id, name, pose, collision_model, settings)

        self.color_camera_params: None | CameraParameters = None

    def color_image(self, *, an: None | str = None) -> Image.Image:
        raise Arcor2NotImplemented()

    def depth_image(self, averaged_frames: int = 1, *, an: None | str = None) -> Image.Image:
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
