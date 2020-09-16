import math
import time
from dataclasses import dataclass
from typing import List, Set, cast

import quaternion  # type: ignore
from pydobot import dobot  # type: ignore

import arcor2.transformations as tr
from arcor2 import DynamicParamTuple as DPT
from arcor2.data.common import ActionMetadata, Joint, Pose, StrEnum
from arcor2.data.robot import RobotType
from arcor2.object_types.abstract import Robot, RobotException, Settings

# TODO jogging


@dataclass
class DobotSettings(Settings):

    port: str = "/dev/dobot"
    calibrate_on_init: bool = False
    simulator: bool = False


class DobotException(RobotException):
    pass


class MoveType(StrEnum):

    JUMP: str = "JUMP"
    JOINTS: str = "JOINTS"
    LINEAR: str = "LINEAR"


MOVE_TYPE_MAPPING = {
    MoveType.JUMP: dobot.MODE_PTP.JUMP_XYZ,
    MoveType.JOINTS: dobot.MODE_PTP.MOVJ_XYZ,
    MoveType.LINEAR: dobot.MODE_PTP.MOVL_XYZ,
}


class AbstractDobot(Robot):

    robot_type = RobotType.SCARA

    def __init__(self, obj_id: str, name: str, pose: Pose, settings: DobotSettings) -> None:
        super(AbstractDobot, self).__init__(obj_id, name, pose, settings)

        if not self.settings.simulator:

            try:
                self._dobot = dobot.Dobot(self.settings.port)
            except dobot.DobotException as e:
                raise DobotException("Could not connect to the robot.") from e

            if self.settings.calibrate_on_init:
                self.home()

        else:

            self._ee_pose = Pose()
            self._ee_pose.orientation.set_from_quaternion(quaternion.from_euler_angles(0, math.pi, 0))

    def alarms_to_exception(self) -> None:

        try:
            alarms = self._dobot.get_alarms()
        except dobot.DobotException as e:
            raise DobotException("Failed to get alarms.") from e

        if alarms:
            raise DobotException(f"Alarm(s): {','.join([alarm.name for alarm in alarms])}.")

    @property
    def settings(self) -> DobotSettings:
        return cast(DobotSettings, super(AbstractDobot, self).settings)

    def cleanup(self):

        if not self.settings.simulator:
            self._dobot.close()

    def get_end_effectors_ids(self) -> Set[str]:
        return {"default"}

    def grippers(self) -> Set[str]:
        return set()

    def suctions(self) -> Set[str]:
        return {"default"}

    def get_end_effector_pose(self, end_effector_id: str) -> Pose:  # global pose

        if self.settings.simulator:
            return tr.make_pose_abs(self.pose, self._ee_pose)

        try:
            pos = self._dobot.get_pose().position  # in mm
        except dobot.DobotException as e:
            raise DobotException("Failed to get pose.") from e

        p = Pose()
        p.position.x = pos.x / 1000.0
        p.position.y = pos.y / 1000.0
        p.position.z = pos.z / 1000.0
        p.orientation.set_from_quaternion(quaternion.from_euler_angles(0, math.pi, pos.r))

        return tr.make_pose_abs(self.pose, p)

    def move_to_pose(self, end_effector_id: str, target_pose: Pose, speed: float) -> None:
        self.move(target_pose, MoveType.LINEAR, speed * 100, 50.0)

    def move_to_joints(self, target_joints: List[Joint], speed: float) -> None:
        raise NotImplementedError("Dobot does not support setting joints so far.")

    def home(self):
        """Run the homing procedure."""

        with self._move_lock:

            if self.settings.simulator:
                time.sleep(2.0)
                return

            try:
                self._dobot.clear_alarms()
                self._dobot.wait_for_cmd(self._dobot.home())
            except dobot.DobotException as e:
                raise DobotException("Homing failed.") from e

        self.alarms_to_exception()

    def move(self, pose: Pose, move_type: MoveType, velocity: float = 50.0, acceleration: float = 50.0) -> None:
        """Moves the robot's end-effector to a specific pose.

        :param pose: Target pose.
        :move_type: Move type.
        :param velocity: Speed of move (percent).
        :param acceleration: Acceleration of move (percent).
        :return:
        """

        assert 0.0 <= velocity <= 100.0
        assert 0.0 <= acceleration <= 100.0

        with self._move_lock:

            rp = tr.make_pose_rel(self.pose, pose)

            if self.settings.simulator:
                time.sleep((100.0 - velocity) * 0.05)
                self._ee_pose = rp
                return

            try:
                self._dobot.clear_alarms()
                rotation = quaternion.as_euler_angles(rp.orientation.as_quaternion())[2]
                self._dobot.speed(velocity, acceleration)
                self._dobot.wait_for_cmd(
                    self._dobot.move_to(
                        rp.position.x * 1000.0,
                        rp.position.y * 1000.0,
                        rp.position.z * 1000.0,
                        rotation,
                        MOVE_TYPE_MAPPING[move_type],
                    )
                )
            except dobot.DobotException as e:
                raise DobotException("Move failed.") from e

        self.alarms_to_exception()

    home.__action__ = ActionMetadata(blocking=True)  # type: ignore
    move.__action__ = ActionMetadata(blocking=True)  # type: ignore


AbstractDobot.DYNAMIC_PARAMS = {
    "end_effector_id": DPT(AbstractDobot.get_end_effectors_ids.__name__, set()),
}
