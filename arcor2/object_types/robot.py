import abc

from arcor2.object_types.generic import Generic
from arcor2.action import action
from arcor2.data.common import ActionMetadata, ActionPoint, Pose
from arcor2.data.object_type import MeshFocusAction


class Robot(Generic, metaclass=abc.ABCMeta):
    """
    Abstract class representing robot and its basic capabilities (motion)
    """

    @abc.abstractmethod
    def get_pose(self, end_effector: str) -> Pose:
        pass

    def focus(self, mfa: MeshFocusAction) -> Pose:
        raise NotImplementedError()