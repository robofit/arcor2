from dataclasses import dataclass
from typing import Optional, cast

from arcor2 import rest
from arcor2.data.common import ActionMetadata, Joint, Pose
from arcor2.object_types.abstract import Robot, RobotException, Settings


@dataclass
class FanucSettings(Settings):

    url: str = "http://fanuc-demo-fanuc-service:5027"


class Fanuc(Robot):
    def __init__(self, obj_id: str, name: str, pose: Pose, settings: FanucSettings) -> None:
        super(Fanuc, self).__init__(obj_id, name, pose, settings)
        self._start()

    def _started(self) -> bool:
        return rest.call(rest.Method.GET, f"{self.settings.url}/state/started", return_type=bool)

    def _stop(self) -> None:
        rest.call(rest.Method.PUT, f"{self.settings.url}/state/stop")

    def _start(self) -> None:

        if self._started():
            self._stop()

        rest.call(
            rest.Method.PUT,
            f"{self.settings.url}/state/start",
            body=self.pose,
        )

    @property
    def settings(self) -> FanucSettings:
        return cast(FanucSettings, super(Fanuc, self).settings)

    def cleanup(self):
        self._stop()

    def get_end_effectors_ids(self) -> set[str]:
        return {"default"}

    def grippers(self) -> set[str]:
        return set("default")

    def suctions(self) -> set[str]:
        return set()

    def get_end_effector_pose(self, end_effector_id: str) -> Pose:
        return rest.call(rest.Method.GET, f"{self.settings.url}/eef/pose", return_type=Pose)

    def move_to_pose(
        self, end_effector_id: str, target_pose: Pose, speed: float, safe: bool = True, linear: bool = True
    ) -> None:
        self.move(target_pose, speed * 100, 50.0, safe, linear)

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

        with self._move_lock:
            rest.call(
                rest.Method.PUT,
                f"{self.settings.url}/eef/pose",
                body=pose,
                params={"velocity": velocity, "acceleration": acceleration, "safe": safe, "linear": linear},
            )

    def gripper_close(self, *, an: Optional[str] = None) -> None:
        """Close the gripper."""
        rest.call(rest.Method.PUT, f"{self.settings.url}/gripper", params={"state": False})

    def gripper_open(self, *, an: Optional[str] = None) -> None:
        """Open the gripper."""

        rest.call(rest.Method.PUT, f"{self.settings.url}/gripper", params={"state": True})

    def gripper_state(self, *, an: Optional[str] = None) -> bool:
        """Checks whether the gripper is open.

        :param an:
        :return:
        """

        return rest.call(rest.Method.GET, f"{self.settings.url}/gripper", return_type=bool)

    def pick(
        self,
        pick_pose: Pose,
        velocity: float = 50.0,
        vertical_offset: float = 0.05,
        safe_approach: bool = True,
        safe_pick: bool = False,
        *,
        an: Optional[str] = None,
    ) -> None:
        """Picks an item from given pose.

        :param pick_pose: Where to pick an object.
        :param velocity: Speed of move (percent).
        :param vertical_offset: Vertical offset for pre/post pick pose.
        :param safe_approach: Safe approach to the pre-pick position.
        :param safe_pick: Safe picking movements.
        :return:
        """

        assert 0.0 <= velocity <= 100.0

        self.gripper_open()

        pick_pose.position.z += vertical_offset
        self.move(pick_pose, velocity, safe=safe_approach)  # pre-pick pose
        pick_pose.position.z -= vertical_offset
        self.move(pick_pose, velocity, safe=safe_pick, linear=True)  # pick pose
        self.gripper_close()
        pick_pose.position.z += vertical_offset
        self.move(pick_pose, velocity, safe=False, linear=True)  # back to pre-pick pose

    def place(
        self,
        place_pose: Pose,
        velocity: float = 50.0,
        vertical_offset: float = 0.05,
        safe_approach: bool = True,
        safe_place: bool = False,
        *,
        an: Optional[str] = None,
    ) -> None:
        """Places an item to a given pose.

        :param place_pose: Where to place the object.
        :param velocity: Speed of move (percent).
        :param vertical_offset: Vertical offset for pre/post place pose.
        :param safe_approach: Safe approach to the pre-pick position.
        :param safe_place: Safe placement movements.
        :return:
        """

        assert 0.0 <= velocity <= 100.0

        if self.gripper_state():
            raise RobotException("Gripper is opened.")

        place_pose.position.z += vertical_offset
        self.move(place_pose, velocity, safe=safe_approach)  # pre-place pose
        place_pose.position.z -= vertical_offset
        self.move(place_pose, velocity, safe=safe_place, linear=True)  # place pose
        self.gripper_open()
        place_pose.position.z += vertical_offset
        self.move(place_pose, velocity, safe=False, linear=True)  # back to pre-place pose

    def robot_joints(self, include_gripper: bool = False) -> list[Joint]:
        return rest.call(rest.Method.GET, f"{self.settings.url}/joints", list_return_type=Joint)

    move.__action__ = ActionMetadata()  # type: ignore
    gripper_open.__action__ = ActionMetadata()  # type: ignore
    gripper_close.__action__ = ActionMetadata()  # type: ignore
    gripper_state.__action__ = ActionMetadata()  # type: ignore
    pick.__action__ = ActionMetadata(composite=True)  # type: ignore
    place.__action__ = ActionMetadata(composite=True)  # type: ignore
