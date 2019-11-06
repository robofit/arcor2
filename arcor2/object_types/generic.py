import abc
from typing import Optional, Dict, Iterator

from arcor2.data.common import Pose, ActionPoint, ActionMetadata
from arcor2.action import action


class Generic(metaclass=abc.ABCMeta):

    __DESCRIPTION__ = "Generic object"

    def __init__(self, name: Optional[str] = None,
                 pose: Optional[Pose] = None) -> None:

        if name is None:
            self.name = type(self).__name__
        else:
            self.name = name

        self.pose = pose
        self.action_points: Dict[str, ActionPoint] = {}

    def add_action_point(self, name: str, pose: Pose) -> None:

        self.action_points[name] = ActionPoint(name, pose)

    def __repr__(self) -> str:
        return str(self.__dict__)

    @action
    def nop(self) -> None:
        pass

    nop.__action__ = ActionMetadata()  # type: ignore
