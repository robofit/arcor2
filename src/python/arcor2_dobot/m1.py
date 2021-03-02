import time
from typing import List

from arcor2_dobot.dobot import Dobot, DobotException
from arcor2_dobot.dobot_api import DobotApiException

from arcor2.data.common import Joint, Pose, StrEnum


class Joints(StrEnum):

    J1: str = "dobot_m1_axis_2_joint"
    J2: str = "dobot_m1_axis_3_joint"
    J3: str = "dobot_m1_z_axis_joint"
    J4: str = "dobot_m1_axis_4_joint"


class DobotM1(Dobot):
    def __init__(self, pose: Pose, port: str = "/dev/dobot", simulator: bool = False) -> None:
        super(DobotM1, self).__init__(pose, port, simulator)

        if self.simulator:
            self._joint_values = [Joint(Joints.J1, 0), Joint(Joints.J2, 0), Joint(Joints.J3, 0), Joint(Joints.J4, 0)]

    def robot_joints(self) -> List[Joint]:

        if self.simulator:
            return self._joint_values

        joints = self._dobot.get_pose().joints.in_radians()
        return [
            Joint(Joints.J1, joints.j1),
            Joint(Joints.J2, joints.j2),
            Joint(Joints.J3, joints.j3),
            Joint(Joints.J4, joints.j4),
        ]

    def suck(self) -> None:

        if self.simulator:
            return

        try:
            self._dobot.set_io(17, False)  # suck
            self._dobot.set_io(18, False)  # on
        except DobotApiException as e:
            raise DobotException("Suck failed.") from e

    def release(self, blow_out_sec: float = 0.1) -> None:

        if self.simulator:
            time.sleep(blow_out_sec)
            return

        try:
            if blow_out_sec > 0:
                self._dobot.set_io(17, True)  # blow
                self._dobot.set_io(18, False)  # on
                time.sleep(blow_out_sec)

            self._dobot.set_io(18, True)  # off

        except DobotApiException as e:
            raise DobotException("Release failed.") from e
