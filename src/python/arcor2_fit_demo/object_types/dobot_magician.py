import os
from typing import List

import arcor2_fit_demo
from arcor2.data.common import Joint, StrEnum

from .abstract_dobot import AbstractDobot


class Joints(StrEnum):

    J1: str = "magician_joint_1"
    J2: str = "magician_joint_2"
    J3: str = "magician_joint_3"
    J4: str = "magician_joint_4"
    J5: str = "magician_joint_5"


class DobotMagician(AbstractDobot):

    _ABSTRACT = False
    urdf_package_path = os.path.join(os.path.dirname(arcor2_fit_demo.__file__), "data", "dobot-magician.zip")

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
