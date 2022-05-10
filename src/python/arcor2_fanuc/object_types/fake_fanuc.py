from typing import Optional

from arcor2.data.common import ActionMetadata, Joint, Pose
from arcor2.object_types.abstract import Robot


class FakeFanuc(Robot):

    _ABSTRACT = False
    urdf_package_name = "fanuc_lrmate200id7l.zip"

    def get_end_effectors_ids(self) -> set[str]:
        return {"default"}

    def grippers(self) -> set[str]:
        return set("default")

    def suctions(self) -> set[str]:
        return set()

    def get_end_effector_pose(self, end_effector_id: str) -> Pose:
        return Pose()

    def move_to_pose(
        self, end_effector_id: str, target_pose: Pose, speed: float, safe: bool = True, linear: bool = True
    ) -> None:
        pass

    def move(
        self,
        pose: Pose,
        velocity: float = 50.0,
        acceleration: float = 50.0,
        safe: bool = True,
        linear: bool = False,
        *,
        an: Optional[str] = None,
    ) -> None:
        """Moves the robot's end-effector to a specific pose.

        :param pose: Target pose.
        :param velocity: Speed of move (percent).
        :param acceleration: Acceleration of move (percent).
        :param safe: When set, the robot will try to avoid collisions.
        :param linear:
        :return:
        """

        assert 0.0 <= velocity <= 100.0
        assert 0.0 <= acceleration <= 100.0

    def robot_joints(self, include_gripper: bool = False) -> list[Joint]:
        return [Joint(f"joint_{x+1}", 0.0) for x in range(6)]

    move.__action__ = ActionMetadata()  # type: ignore
