from typing import Set

from arcor2.data.common import Pose
from arcor2.exceptions import Arcor2NotImplemented
from arcor2.object_types.abstract import RobotType

from .abstract_robot import AbstractRobot


class Simatic(AbstractRobot):
    """REST interface to the robot service (0.7.0)."""

    _ABSTRACT = False
    robot_type = RobotType.CARTESIAN

    def get_end_effectors_ids(self) -> Set[str]:
        return set()

    def get_end_effector_pose(self, end_effector: str) -> Pose:
        raise Arcor2NotImplemented("Not supported")

    def suctions(self) -> Set[str]:
        return set()
