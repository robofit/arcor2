from arcor2.data.common import Joint, Pose, StrEnum

from .abstract_dobot import AbstractDobot, DobotSettings, MoveType


class Joints(StrEnum):

    J1: str = "magician_joint_1"
    J2: str = "magician_joint_2"
    J3: str = "magician_joint_3"
    J4: str = "magician_joint_4"
    J5: str = "magician_joint_5"


class DobotMagician(AbstractDobot):

    _ABSTRACT = False
    urdf_package_name = "dobot-magician.zip"

    def __init__(self, obj_id: str, name: str, pose: Pose, settings: DobotSettings) -> None:
        super(DobotMagician, self).__init__(obj_id, name, pose, settings)
        self._start("magician")

    def move_to_calibration_pose(self) -> None:

        joint_values = [  # TODO define as pose
            Joint(Joints.J1, -0.0115),
            Joint(Joints.J2, 0.638),
            Joint(Joints.J3, -0.5486),
            Joint(Joints.J4, -0.0898),
            Joint(Joints.J5, 1.41726),
        ]

        self.move(self.forward_kinematics("", joint_values), MoveType.LINEAR, 50)
