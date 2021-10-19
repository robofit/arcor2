from dataclasses import dataclass
from typing import List, Optional, Set, cast

from arcor2 import DynamicParamTuple as DPT
from arcor2 import rest
from arcor2.data.common import ActionMetadata, Joint, Pose, StrEnum
from arcor2.data.robot import RobotType
from arcor2.object_types.abstract import Robot, RobotException

from .fit_common_mixin import FitCommonMixin, UrlSettings


@dataclass
class DobotSettings(UrlSettings):

    port: str = "/dev/dobot"


class DobotException(RobotException):
    pass


class MoveType(StrEnum):

    JUMP: str = "JUMP"
    JOINTS: str = "JOINTS"
    LINEAR: str = "LINEAR"


class AbstractDobot(FitCommonMixin, Robot):

    robot_type = RobotType.SCARA

    def __init__(self, obj_id: str, name: str, pose: Pose, settings: DobotSettings) -> None:
        super(AbstractDobot, self).__init__(obj_id, name, pose, settings)

    def _start(self, model: str) -> None:

        if self._started():
            self._stop()

        rest.call(
            rest.Method.PUT,
            f"{self.settings.url}/state/start",
            params={"model": model, "port": self.settings.port},
            body=self.pose,
        )

    @property
    def settings(self) -> DobotSettings:  # type: ignore
        return cast(DobotSettings, super(AbstractDobot, self).settings)

    def cleanup(self):
        self._stop()

    def get_end_effectors_ids(self) -> Set[str]:
        return {"default"}

    def grippers(self) -> Set[str]:
        return set()

    def suctions(self) -> Set[str]:
        return {"default"}

    def get_end_effector_pose(self, end_effector_id: str) -> Pose:
        return rest.call(rest.Method.GET, f"{self.settings.url}/eef/pose", return_type=Pose)

    def move_to_pose(
        self, end_effector_id: str, target_pose: Pose, speed: float, safe: bool = True, linear: bool = True
    ) -> None:
        if safe:
            raise DobotException("Dobot does not support safe moves.")
        self.move(target_pose, MoveType.LINEAR if linear else MoveType.JOINTS, speed * 100)

    def move_to_joints(self, target_joints: List[Joint], speed: float, safe: bool = True) -> None:
        if safe:
            raise DobotException("Dobot does not support safe moves.")
        self.move(self.forward_kinematics("", target_joints), MoveType.LINEAR, speed * 100)

    def home(self, *, an: Optional[str] = None) -> None:
        """Run the homing procedure."""
        with self._move_lock:
            rest.call(rest.Method.PUT, f"{self.settings.url}/home")

    def move(
        self,
        pose: Pose,
        move_type: MoveType,
        velocity: float = 50.0,
        acceleration: float = 50.0,
        *,
        an: Optional[str] = None,
    ) -> None:
        """Moves the robot's end-effector to a specific pose.

        :param pose: Target pose.
        :param move_type: Move type.
        :param velocity: Speed of move (percent).
        :param acceleration: Acceleration of move (percent).
        :return:
        """

        assert 0.0 <= velocity <= 100.0
        assert 0.0 <= acceleration <= 100.0

        with self._move_lock:
            rest.call(
                rest.Method.PUT,
                f"{self.settings.url}/eef/pose",
                body=pose,
                params={"move_type": move_type, "velocity": velocity, "acceleration": acceleration},
            )

    def suck(self, *, an: Optional[str] = None) -> None:
        """Turns on the suction."""
        rest.call(rest.Method.PUT, f"{self.settings.url}/suck")

    def release(self, *, an: Optional[str] = None) -> None:
        """Turns off the suction."""

        rest.call(rest.Method.PUT, f"{self.settings.url}/release")

    def pick(self, pick_pose: Pose, vertical_offset: float = 0.05, *, an: Optional[str] = None) -> None:
        """Picks an item from given pose.

        :param pick_pose: Where to pick an object.
        :param vertical_offset: Vertical offset for pre/post pick pose.
        :return:
        """

        pick_pose.position.z += vertical_offset
        self.move(pick_pose, MoveType.JOINTS)  # pre-pick pose
        pick_pose.position.z -= vertical_offset
        self.move(pick_pose, MoveType.JOINTS)  # pick pose
        self.suck()
        pick_pose.position.z += vertical_offset
        self.move(pick_pose, MoveType.JOINTS)  # pre-pick pose

    def place(self, place_pose: Pose, vertical_offset: float = 0.05, *, an: Optional[str] = None) -> None:
        """Places an item to a given pose.

        :param place_pose: Where to place the object.
        :param vertical_offset: Vertical offset for pre/post place pose.
        :return:
        """

        place_pose.position.z += vertical_offset
        self.move(place_pose, MoveType.JOINTS)  # pre-place pose
        place_pose.position.z -= vertical_offset
        self.move(place_pose, MoveType.JOINTS)  # place pose
        self.release()
        place_pose.position.z += vertical_offset
        self.move(place_pose, MoveType.JOINTS)  # pre-place pose

    def robot_joints(self, include_gripper: bool = False) -> List[Joint]:
        return rest.call(rest.Method.GET, f"{self.settings.url}/joints", list_return_type=Joint)

    home.__action__ = ActionMetadata()  # type: ignore
    move.__action__ = ActionMetadata()  # type: ignore
    suck.__action__ = ActionMetadata()  # type: ignore
    release.__action__ = ActionMetadata()  # type: ignore
    pick.__action__ = ActionMetadata(composite=True)  # type: ignore
    place.__action__ = ActionMetadata(composite=True)  # type: ignore


AbstractDobot.DYNAMIC_PARAMS = {
    "end_effector_id": DPT(AbstractDobot.get_end_effectors_ids.__name__, set()),
}
