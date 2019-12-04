import abc
from typing import Set, List

from arcor2.object_types.generic import Generic
from arcor2.data.common import Pose, Joint


class Robot(Generic, metaclass=abc.ABCMeta):
    """
    Abstract class representing robot and its basic capabilities (motion)
    """

    @abc.abstractmethod
    def get_end_effectors_ids(self) -> Set[str]:
        pass

    @abc.abstractmethod
    def get_end_effector_pose(self, end_effector: str) -> Pose:
        pass

    @abc.abstractmethod
    def robot_joints(self) -> List[Joint]:
        pass
