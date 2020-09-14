from typing import List

from arcor2.data.common import Joint, StrEnum

from .abstract_dobot import AbstractDobot


class Joints(StrEnum):

    J1: str = "dobot_m1_z_axis_joint"
    J2: str = "dobot_m1_axis_2_joint"
    J3: str = "dobot_m1_axis_3_joint"
    J4: str = "dobot_m1_axis_4_joint"


class DobotM1(AbstractDobot):

    _ABSTRACT = False
    # urdf_package_path = os.path.join(os.path.dirname(arcor2_fit_demo.__file__), "data", "dobot-m1.zip")

    def robot_joints(self) -> List[Joint]:

        if self.settings.simulator:
            return [Joint(Joints.J1, 0), Joint(Joints.J2, 0), Joint(Joints.J3, 0), Joint(Joints.J4, 0)]

        joints = self._dobot.get_pose().joints.in_radians()
        return [
            Joint(Joints.J1, joints.j1),
            Joint(Joints.J2, joints.j2),
            Joint(Joints.J3, joints.j3),
            Joint(Joints.J4, joints.j4),
        ]
