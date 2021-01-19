import math
import time
from abc import ABCMeta, abstractmethod
from typing import List

import quaternion
from pydobot import dobot

import arcor2.transformations as tr
from arcor2.data.common import Joint, Pose, StrEnum
from arcor2.exceptions import Arcor2NotImplemented
from arcor2.helpers import NonBlockingLock
from arcor2.object_types.abstract import RobotException

# TODO jogging


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


class Dobot(metaclass=ABCMeta):
    def __init__(self, pose: Pose, port: str = "/dev/dobot", simulator: bool = False) -> None:

        self.pose = pose
        self.simulator = simulator
        self._move_lock = NonBlockingLock()

        if not self.simulator:

            try:
                self._dobot = dobot.Dobot(port)
            except dobot.DobotException as e:
                raise DobotException("Could not connect to the robot.") from e

        else:
            self._joint_values: List[Joint] = []  # has to be set to some initial value in derived classes

    def alarms_to_exception(self) -> None:

        try:
            alarms = self._dobot.get_alarms()
        except dobot.DobotException as e:
            raise DobotException("Failed to get alarms.") from e

        if alarms:
            raise DobotException(f"Alarm(s): {','.join([alarm.name for alarm in alarms])}.")

    def cleanup(self):

        if not self.simulator:
            self._dobot.close()

    def _inverse_kinematics(self, pose: Pose) -> List[Joint]:
        raise Arcor2NotImplemented()

    def inverse_kinematics(self, pose: Pose) -> List[Joint]:
        raise Arcor2NotImplemented()

    def forward_kinematics(self, joints: List[Joint]) -> Pose:
        raise Arcor2NotImplemented()

    def _handle_pose_out(self, pose: Pose) -> None:
        """This is called (only for a real robot) from `get_end_effector_pose`
        so derived classes can do custom changes to the pose.

        :param pose:
        :return:
        """

        pass

    def _handle_pose_in(self, pose: Pose) -> None:
        """This is called (only for a real robot) from `move` so derived
        classes can do custom changes to the pose.

        :param pose:
        :return:
        """

        pass

    def _check_orientation(self, pose: Pose) -> None:

        x = math.sin(math.atan2(pose.orientation.x, pose.orientation.w))
        y = math.sin(math.atan2(pose.orientation.y, pose.orientation.w))

        eps = 1e-6

        if (abs(x) > eps and 1 - abs(x) > eps) or 1 - abs(y) > eps:
            raise DobotException("Impossible orientation.")

    def get_end_effector_pose(self) -> Pose:

        if self.simulator:
            return self.forward_kinematics(self._joint_values)

        try:
            pos = self._dobot.get_pose()  # in mm
        except dobot.DobotException as e:
            raise DobotException("Failed to get pose.") from e

        p = Pose()
        p.position.x = pos.position.x / 1000.0
        p.position.y = pos.position.y / 1000.0
        p.position.z = pos.position.z / 1000.0
        p.orientation.set_from_quaternion(
            quaternion.from_euler_angles(0, math.pi, math.radians(pos.joints.j4 + pos.joints.j1))
        )

        self._handle_pose_out(p)
        return tr.make_pose_abs(self.pose, p)

    def home(self):
        """Run the homing procedure."""

        with self._move_lock:

            if self.simulator:
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

        if not (0.0 <= velocity <= 100.0):
            raise DobotException("Invalid velocity.")

        if not (0.0 <= acceleration <= 100.0):
            raise DobotException("Invalid acceleration.")

        with self._move_lock:

            rp = tr.make_pose_rel(self.pose, pose)

            # prevent Dobot from moving when given an unreachable goal
            try:
                jv = self._inverse_kinematics(rp)
            except Arcor2NotImplemented:  # TODO remove this once M1 has IK
                pass

            if self.simulator:
                self._joint_values = jv
                time.sleep((100.0 - velocity) * 0.05)
                return

            self._handle_pose_in(rp)

            try:
                self._dobot.clear_alarms()

                # TODO this is probably not working properly (use similar solution as in _check_orientation?)
                rotation = math.degrees(quaternion.as_euler_angles(rp.orientation.as_quaternion())[2])
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

    @abstractmethod
    def suck(self) -> None:
        pass

    @abstractmethod
    def release(self) -> None:
        pass

    @abstractmethod
    def robot_joints(self) -> List[Joint]:
        pass
