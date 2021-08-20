from typing import List, Optional, Set

from arcor2.data.common import Joint, Pose
from arcor2.object_types.abstract import Robot, Settings

from .logging_mixin import LoggingMixin


class LoggingTestRobot(LoggingMixin, Robot):
    def __init__(self, obj_id: str, name: str, pose: Pose, settings: Optional[Settings] = None) -> None:
        super().__init__(obj_id, name, pose, settings)
        self.logger = self.get_logger()
        self.logger.info("Initialized.")

    def get_end_effectors_ids(self) -> Set[str]:
        return set()

    def get_end_effector_pose(self, end_effector: str) -> Pose:
        return Pose()

    def robot_joints(self, include_gripper: bool = False) -> List[Joint]:
        return []

    def grippers(self) -> Set[str]:
        return set()

    def suctions(self) -> Set[str]:
        return set()
