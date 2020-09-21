from typing import List

from pydobot import dobot  # type: ignore

from arcor2.data.common import ActionMetadata, Joint, StrEnum

from .abstract_dobot import AbstractDobot, DobotException


class Joints(StrEnum):

    J1: str = "magician_joint_1"
    J2: str = "magician_joint_2"
    J3: str = "magician_joint_3"
    J4: str = "magician_joint_4"
    J5: str = "magician_joint_5"


class DobotMagician(AbstractDobot):

    _ABSTRACT = False
    urdf_package_name = "dobot-magician.zip"

    def robot_joints(self) -> List[Joint]:

        if self.settings.simulator:
            return [
                Joint(Joints.J1, 0),
                Joint(Joints.J2, 0),
                Joint(Joints.J3, 0),
                Joint(Joints.J4, 0),
                Joint(Joints.J5, 0),
            ]

        joints = self._dobot.get_pose().joints.in_radians()
        return [
            Joint(Joints.J1, joints.j1),
            Joint(Joints.J2, joints.j2),
            Joint(Joints.J3, joints.j3 - joints.j2),
            Joint(Joints.J4, -joints.j3),
            Joint(Joints.J5, joints.j4),
        ]

    def suck(self) -> None:

        if self.settings.simulator:
            return

        try:
            self._dobot.wait_for_cmd(self._dobot.suck(True))
        except dobot.DobotException as e:
            raise DobotException("Suck failed.") from e

    def release(self) -> None:

        if self.settings.simulator:
            return

        try:
            self._dobot.wait_for_cmd(self._dobot.suck(False))
        except dobot.DobotException as e:
            raise DobotException("Release failed.") from e

    suck.__action__ = ActionMetadata(blocking=True)  # type: ignore
    release.__action__ = ActionMetadata(blocking=True)  # type: ignore
