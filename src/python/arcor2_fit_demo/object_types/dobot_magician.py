from dataclasses import dataclass

from arcor2 import rest
from arcor2.data.common import Joint, Pose, StrEnum

from .abstract_dobot import AbstractDobot, MoveType  # noqa:ABS101
from .fit_common_mixin import UrlSettings  # noqa:ABS101


class Joints(StrEnum):

    J1: str = "magician_joint_1"
    J2: str = "magician_joint_2"
    J3: str = "magician_joint_3"
    J4: str = "magician_joint_4"
    J5: str = "magician_joint_5"


@dataclass
class MagicianSettings(UrlSettings):

    url: str = "http://fit-demo-dobot-magician:5018"


class DobotMagician(AbstractDobot):

    _ABSTRACT = False
    urdf_package_name = "dobot-magician.zip"

    def __init__(self, obj_id: str, name: str, pose: Pose, settings: MagicianSettings) -> None:
        super(DobotMagician, self).__init__(obj_id, name, pose, settings)
        self._start()

    def move_to_calibration_pose(self) -> None:

        joint_values = [  # TODO define as pose
            Joint(Joints.J1, -0.0115),
            Joint(Joints.J2, 0.638),
            Joint(Joints.J3, -0.5486),
            Joint(Joints.J4, -0.0898),
            Joint(Joints.J5, 1.41726),
        ]

        self.move(self.forward_kinematics("", joint_values), MoveType.LINEAR, 50)

    def inverse_kinematics(
        self,
        end_effector_id: str,
        pose: Pose,
        start_joints: None | list[Joint] = None,
        avoid_collisions: bool = True,
    ) -> list[Joint]:
        """Computes inverse kinematics.

        :param end_effector_id: IK target pose end-effector
        :param pose: IK target pose
        :param start_joints: IK start joints (not supported)
        :param avoid_collisions: Return non-collision IK result if true (not supported)
        :return: Inverse kinematics
        """

        return rest.call(rest.Method.PUT, f"{self.settings.url}/ik", body=pose, list_return_type=Joint)

    def forward_kinematics(self, end_effector_id: str, joints: list[Joint]) -> Pose:
        """Computes forward kinematics.

        :param end_effector_id: Target end effector name
        :param joints: Input joint values
        :return: Pose of the given end effector
        """

        return rest.call(rest.Method.PUT, f"{self.settings.url}/fk", body=joints, return_type=Pose)
