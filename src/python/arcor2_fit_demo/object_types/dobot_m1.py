import time
from typing import List

from pydobot import dobot

from arcor2.data.common import ActionMetadata, Joint, Pose, StrEnum

from .abstract_dobot import AbstractDobot, DobotException, DobotSettings


class Joints(StrEnum):

    J1: str = "dobot_m1_z_axis_joint"
    J2: str = "dobot_m1_axis_2_joint"
    J3: str = "dobot_m1_axis_3_joint"
    J4: str = "dobot_m1_axis_4_joint"


class DobotM1(AbstractDobot):

    _ABSTRACT = False
    urdf_package_name = "dobot-m1.zip"

    def __init__(self, obj_id: str, name: str, pose: Pose, settings: DobotSettings) -> None:
        super(DobotM1, self).__init__(obj_id, name, pose, settings)

        if self.settings.simulator:
            self._joint_values = [Joint(Joints.J1, 0), Joint(Joints.J2, 0), Joint(Joints.J3, 0), Joint(Joints.J4, 0)]

    def robot_joints(self) -> List[Joint]:

        if self.settings.simulator:
            return self._joint_values

        joints = self._dobot.get_pose().joints.in_radians()
        return [
            Joint(Joints.J1, joints.j1),
            Joint(Joints.J2, joints.j2),
            Joint(Joints.J3, joints.j3),
            Joint(Joints.J4, joints.j4),
        ]

    def suck(self) -> None:

        if self.settings.simulator:
            return

        try:
            self._dobot.set_io(17, False)  # suck
            self._dobot.set_io(18, False)  # on
        except dobot.DobotException as e:
            raise DobotException("Suck failed.") from e

    def release(self, blow_out_sec: float = 0.1) -> None:

        assert 0.0 <= blow_out_sec <= 60.0

        if self.settings.simulator:
            time.sleep(blow_out_sec)
            return

        try:
            if blow_out_sec > 0:
                self._dobot.set_io(17, True)  # blow
                self._dobot.set_io(18, False)  # on
                time.sleep(blow_out_sec)

            self._dobot.set_io(18, True)  # off

        except dobot.DobotException as e:
            raise DobotException("Release failed.") from e

    suck.__action__ = ActionMetadata(blocking=True)  # type: ignore
    release.__action__ = ActionMetadata(blocking=True)  # type: ignore
