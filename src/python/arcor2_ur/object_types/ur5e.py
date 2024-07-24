from dataclasses import dataclass
from typing import cast

from arcor2 import rest
from arcor2.data.common import ActionMetadata, Joint, Pose
from arcor2.data.robot import InverseKinematicsRequest
from arcor2.object_types.abstract import Robot, Settings


@dataclass
class UrSettings(Settings):
    url: str = "http://ur-demo-robot-api:5012"


class Ur5e(Robot):
    _ABSTRACT = False
    urdf_package_name = "ur5e.zip"

    def __init__(self, obj_id: str, name: str, pose: Pose, settings: UrSettings) -> None:
        super(Ur5e, self).__init__(obj_id, name, pose, settings)
        self._start()

    def _started(self) -> bool:
        return rest.call(rest.Method.GET, f"{self.settings.url}/state/started", return_type=bool)

    def _stop(self) -> None:
        rest.call(rest.Method.PUT, f"{self.settings.url}/state/stop")

    def _start(self) -> None:
        if self._started():
            self._stop()

        rest.call(rest.Method.PUT, f"{self.settings.url}/state/start", body=self.pose, timeout=rest.Timeout(read=30))

    @property
    def settings(self) -> UrSettings:
        return cast(UrSettings, super(Ur5e, self).settings)

    def cleanup(self):
        self._stop()

    def get_end_effectors_ids(self) -> set[str]:
        return {"default"}

    def grippers(self) -> set[str]:
        return set()

    def suctions(self) -> set[str]:
        return set("default")

    def get_end_effector_pose(self, end_effector_id: str) -> Pose:
        return rest.call(rest.Method.GET, f"{self.settings.url}/eef/pose", return_type=Pose)

    def move_to_pose(
        self, end_effector_id: str, target_pose: Pose, speed: float, safe: bool = True, linear: bool = True
    ) -> None:
        self.move(target_pose)

    def move(
        self,
        pose: Pose,
        *,
        an: None | str = None,
    ) -> None:
        """Moves the robot's end-effector to a specific pose.

        :param pose: Target pose.
        :return:
        """

        with self._move_lock:
            rest.call(
                rest.Method.PUT,
                f"{self.settings.url}/eef/pose",
                body=pose,
            )

    def robot_joints(self, include_gripper: bool = False) -> list[Joint]:
        return rest.call(rest.Method.GET, f"{self.settings.url}/joints", list_return_type=Joint)

    def inverse_kinematics(
        self,
        end_effector_id: str,
        pose: Pose,
        start_joints: None | list[Joint] = None,
        avoid_collisions: bool = True,
    ) -> list[Joint]:
        """Computes inverse kinematics.

        :param end_effector_id: IK target pose end-effector
        :param pose: IK target pose
        :param start_joints: IK start joints (not supported)
        :param avoid_collisions: Return non-collision IK result if true (not supported)
        :return: Inverse kinematics
        """

        return rest.call(
            rest.Method.PUT,
            f"{self.settings.url}/ik",
            body=InverseKinematicsRequest(pose, start_joints, avoid_collisions),
            list_return_type=Joint,
        )

    move.__action__ = ActionMetadata()  # type: ignore
