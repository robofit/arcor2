from arcor2 import DynamicParamTuple as DPT
from arcor2 import rest
from arcor2.data.common import ActionMetadata, Joint, Pose, StrEnum
from arcor2.data.robot import RobotType
from arcor2.object_types.abstract import Robot, RobotException

from .fit_common_mixin import FitCommonMixin  # noqa:ABS101


class DobotException(RobotException):
    pass


class MoveType(StrEnum):

    JUMP: str = "JUMP"
    JOINTS: str = "JOINTS"
    LINEAR: str = "LINEAR"


class AbstractDobot(FitCommonMixin, Robot):

    robot_type = RobotType.SCARA

    def _start(self) -> None:

        if self._started():
            self._stop()

        rest.call(
            rest.Method.PUT,
            f"{self.settings.url}/state/start",
            body=self.pose,
        )

    def cleanup(self):
        self._stop()

    def get_end_effectors_ids(self) -> set[str]:
        return {"default"}

    def grippers(self) -> set[str]:
        return set()

    def suctions(self) -> set[str]:
        return {"default"}

    def get_end_effector_pose(self, end_effector_id: str) -> Pose:
        return rest.call(rest.Method.GET, f"{self.settings.url}/eef/pose", return_type=Pose)

    def move_to_pose(
        self, end_effector_id: str, target_pose: Pose, speed: float, safe: bool = True, linear: bool = True
    ) -> None:
        self.move(target_pose, MoveType.LINEAR if linear else MoveType.JOINTS, speed * 100, safe=safe)

    def move_to_joints(self, target_joints: list[Joint], speed: float, safe: bool = True) -> None:
        self.move(self.forward_kinematics("", target_joints), MoveType.LINEAR, speed * 100, safe=safe)

    def home(self, *, an: None | str = None) -> None:
        """Run the homing procedure."""
        with self._move_lock:
            rest.call(rest.Method.PUT, f"{self.settings.url}/home")

    def move(
        self,
        pose: Pose,
        move_type: MoveType,
        velocity: float = 50.0,
        acceleration: float = 50.0,
        safe: bool = True,
        *,
        an: None | str = None,
    ) -> None:
        """Moves the robot's end-effector to a specific pose.

        :param pose: Target pose.
        :param move_type: Move type.
        :param velocity: Speed of move (percent).
        :param acceleration: Acceleration of move (percent).
        :param safe: When set, the robot will try to avoid collisions.
        :return:
        """

        assert 0.0 <= velocity <= 100.0
        assert 0.0 <= acceleration <= 100.0

        with self._move_lock:
            rest.call(
                rest.Method.PUT,
                f"{self.settings.url}/eef/pose",
                body=pose,
                params={"move_type": move_type, "velocity": velocity, "acceleration": acceleration, "safe": safe},
            )

    def suck(self, *, an: None | str = None) -> None:
        """Turns on the suction."""
        rest.call(rest.Method.PUT, f"{self.settings.url}/suck")

    def release(self, *, an: None | str = None) -> None:
        """Turns off the suction."""

        rest.call(rest.Method.PUT, f"{self.settings.url}/release")

    def pick(
        self,
        pick_pose: Pose,
        velocity: float = 50.0,
        vertical_offset: float = 0.05,
        safe_approach: bool = True,
        safe_pick: bool = False,
        *,
        an: None | str = None,
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

        pick_pose.position.z += vertical_offset
        self.move(pick_pose, MoveType.JOINTS, velocity, safe=safe_approach)  # pre-pick pose
        pick_pose.position.z -= vertical_offset
        self.move(pick_pose, MoveType.LINEAR, velocity, safe=safe_pick)  # pick pose
        self.suck()
        pick_pose.position.z += vertical_offset
        self.move(pick_pose, MoveType.LINEAR, velocity, safe=False)  # back to pre-pick pose

    def place(
        self,
        place_pose: Pose,
        velocity: float = 50.0,
        vertical_offset: float = 0.05,
        safe_approach: bool = True,
        safe_place: bool = False,
        *,
        an: None | str = None,
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

        place_pose.position.z += vertical_offset
        self.move(place_pose, MoveType.JOINTS, velocity, safe=safe_approach)  # pre-place pose
        place_pose.position.z -= vertical_offset
        self.move(place_pose, MoveType.LINEAR, velocity, safe=safe_place)  # place pose
        self.release()
        place_pose.position.z += vertical_offset
        self.move(place_pose, MoveType.LINEAR, velocity, safe=False)  # back to pre-place pose

    def robot_joints(self, include_gripper: bool = False) -> list[Joint]:
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
