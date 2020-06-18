import abc
from typing import FrozenSet, List, Optional

from arcor2.object_types.generic import Generic
from arcor2.data.common import Pose, Joint, ProjectRobotJoints


class Robot(Generic, metaclass=abc.ABCMeta):
    """
    Abstract class representing robot and its basic capabilities (motion)
    """

    urdf_package_path: Optional[str] = None

    @abc.abstractmethod
    def get_end_effectors_ids(self) -> FrozenSet[str]:
        pass

    @abc.abstractmethod
    def get_end_effector_pose(self, end_effector: str) -> Pose:
        pass

    @abc.abstractmethod
    def robot_joints(self) -> List[Joint]:
        pass

    @abc.abstractmethod
    def grippers(self) -> FrozenSet[str]:
        return frozenset()

    @abc.abstractmethod
    def suctions(self) -> FrozenSet[str]:
        return frozenset()

    @abc.abstractmethod
    def move_to_pose(self, target_pose: Pose, end_effector: str, speed: float) -> None:
        """
        Move given robot's end effector to the selected pose.
        :param target_pose:
        :param end_effector:
        :param speed:
        :return:
        """

        assert .0 <= speed <= 1.

    @abc.abstractmethod
    def move_to_joints(self, target_joints: ProjectRobotJoints, speed: float) -> None:
        """
        Sets target joint values.
        :param target_joints:
        :param speed:
        :return:
        """

        assert .0 <= speed <= 1.
