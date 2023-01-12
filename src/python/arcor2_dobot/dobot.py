import math
import time
from abc import ABCMeta, abstractmethod

import quaternion

import arcor2.transformations as tr
from arcor2.data.common import Joint, Orientation, Pose, StrEnum
from arcor2.exceptions import Arcor2NotImplemented
from arcor2.helpers import NonBlockingLock
from arcor2.object_types.abstract import RobotException
from arcor2_dobot.dobot_api import MODE_PTP, DobotApi, DobotApiException

# TODO jogging


class DobotException(RobotException):
    pass


class MoveType(StrEnum):

    JUMP: str = "JUMP"
    JOINTS: str = "JOINTS"
    LINEAR: str = "LINEAR"


MOVE_TYPE_MAPPING = {
    MoveType.JUMP: MODE_PTP.JUMP_XYZ,
    MoveType.JOINTS: MODE_PTP.MOVJ_XYZ,
    MoveType.LINEAR: MODE_PTP.MOVL_XYZ,
}


class Dobot(metaclass=ABCMeta):

    ROTATE_EEF = Orientation.from_rotation_vector(y=math.pi)
    UNROTATE_EEF = ROTATE_EEF.inversed()

    def __init__(self, pose: Pose, port: str = "/dev/dobot", simulator: bool = False) -> None:

        self.pose = pose
        self.simulator = simulator
        self._move_lock = NonBlockingLock()

        if not self.simulator:

            try:
                self._dobot = DobotApi(port)
            except DobotApiException as e:
                raise DobotApiException("Could not connect to the robot.") from e

        else:
            self._joint_values: list[Joint] = []  # has to be set to some initial value in derived classes
            self._hand_teaching = False

    def alarms_to_exception(self) -> None:

        try:
            alarms = self._dobot.get_alarms()
        except DobotApiException as e:
            raise DobotApiException("Failed to get alarms.") from e

        if alarms:
            raise DobotApiException(f"Alarm(s): {','.join([alarm.name for alarm in alarms])}.")

    def cleanup(self) -> None:

        self.conveyor_speed(0)
        self.release()

        if not self.simulator:
            self._dobot.close()

    def conveyor_speed(self, speed: float, direction: int = 1) -> None:

        if not self.simulator:
            self._dobot.conveyor_belt(speed, direction)

    def conveyor_distance(self, speed: float, distance: float, direction: int = 1) -> None:
        self._dobot.conveyor_belt_distance(speed, distance, direction)

    @property
    def hand_teaching_mode(self) -> bool:

        if self.simulator:
            return self._hand_teaching

        return self._dobot.get_hht_trig_output()

    @hand_teaching_mode.setter
    def hand_teaching_mode(self, value: bool) -> None:

        if self.simulator:
            self._hand_teaching = value
            return

        self._dobot.set_hht_trig_output(value)

    def _inverse_kinematics(self, pose: Pose) -> list[Joint]:
        raise Arcor2NotImplemented("IK not implemented.")

    def inverse_kinematics(self, pose: Pose) -> list[Joint]:
        raise Arcor2NotImplemented("IK not implemented.")

    def forward_kinematics(self, joints: list[Joint]) -> Pose:
        raise Arcor2NotImplemented("FK not implemented.")

    def _handle_pose_out(self, pose: Pose) -> None:  # noqa:B027
        """This is called (only for a real robot) from `get_end_effector_pose`
        so derived classes can do custom changes to the pose.

        :param pose:
        :return:
        """

        pass

    def _handle_pose_in(self, pose: Pose) -> None:  # noqa:B027
        """This is called (only for a real robot) from `move` so derived
        classes can do custom changes to the pose.

        :param pose:
        :return:
        """

        pass

    def _check_orientation(self, pose: Pose) -> None:

        unrotated = self.UNROTATE_EEF * pose.orientation

        eps = 1e-6

        if abs(unrotated.x) > eps or abs(unrotated.y) > eps:
            raise DobotApiException("Impossible orientation.")

    def get_end_effector_pose(self) -> Pose:

        if self.simulator:
            return self.forward_kinematics(self.robot_joints())

        try:
            pos = self._dobot.get_pose()  # in mm
        except DobotApiException as e:
            raise DobotException("Failed to get pose.") from e

        p = Pose()
        p.position.x = pos.position.x / 1000.0
        p.position.y = pos.position.y / 1000.0
        p.position.z = pos.position.z / 1000.0
        p.orientation = self.ROTATE_EEF * Orientation.from_rotation_vector(z=math.radians(pos.position.r))

        self._handle_pose_out(p)
        return tr.make_pose_abs(self.pose, p)

    def home(self) -> None:
        """Run the homing procedure."""

        with self._move_lock:

            if self.simulator:
                time.sleep(2.0)
                return

            try:
                self._dobot.clear_alarms()
                self._dobot.wait_for_cmd(self._dobot.home())
            except DobotApiException as e:
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
                unrotated = self.UNROTATE_EEF * rp.orientation
                rotation = math.degrees(quaternion.as_rotation_vector(unrotated.as_quaternion())[2])
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
            except DobotApiException as e:
                raise DobotException("Move failed.") from e

        self.alarms_to_exception()

    @abstractmethod
    def suck(self) -> None:
        pass

    @abstractmethod
    def release(self) -> None:
        pass

    @abstractmethod
    def robot_joints(self) -> list[Joint]:
        pass
