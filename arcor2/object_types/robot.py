import abc
from typing import FrozenSet, List, Optional

from arcor2.object_types.generic import Generic
from arcor2.data.common import Pose, Joint


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
