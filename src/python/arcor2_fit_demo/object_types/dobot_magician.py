import math
from typing import Dict, List, Optional, Tuple

import quaternion
from pydobot import dobot

import arcor2.transformations as tr
from arcor2.data.common import ActionMetadata, Joint, Orientation, Pose, Position, StrEnum

from .abstract_dobot import AbstractDobot, DobotException, DobotSettings, MoveType


class Joints(StrEnum):

    J1: str = "magician_joint_1"
    J2: str = "magician_joint_2"
    J3: str = "magician_joint_3"
    J4: str = "magician_joint_4"
    J5: str = "magician_joint_5"


class DobotMagician(AbstractDobot):

    _ABSTRACT = False
    urdf_package_name = "dobot-magician.zip"

    # Dimensions in meters (according to URDF)
    link_2_length = 0.135
    link_3_length = 0.147
    link_4_length = 0.06
    end_effector_length = 0.06

    def __init__(self, obj_id: str, name: str, pose: Pose, settings: DobotSettings) -> None:
        super(DobotMagician, self).__init__(obj_id, name, pose, settings)

        if self.settings.simulator:
            self._joint_values = [
                Joint(Joints.J1, -0.038),
                Joint(Joints.J2, 0.341),
                Joint(Joints.J3, 0.3632),
                Joint(Joints.J4, -0.704),
                Joint(Joints.J5, -0.568),
            ]

    def move_to_calibration_pose(self) -> None:

        joint_values = [
            Joint(Joints.J1, -0.0115),
            Joint(Joints.J2, 0.638),
            Joint(Joints.J3, -0.5486),
            Joint(Joints.J4, -0.0898),
            Joint(Joints.J5, 1.41726),
        ]

        self.move(self.forward_kinematics("", joint_values), MoveType.LINEAR, 50)

    def _handle_pose_in(self, pose: Pose) -> None:

        base_angle = math.atan2(pose.position.y, pose.position.x)
        pose.position.x -= self.link_4_length * math.cos(base_angle)
        pose.position.y -= self.link_4_length * math.sin(base_angle)
        pose.position.z += self.end_effector_length

    def _handle_pose_out(self, pose: Pose) -> None:

        base_angle = math.atan2(pose.position.y, pose.position.x)
        pose.position.x += self.link_4_length * math.cos(base_angle)
        pose.position.y += self.link_4_length * math.sin(base_angle)
        pose.position.z -= self.end_effector_length

    # TODO joint4/5
    valid_ranges: Dict[Joints, Tuple[float, float]] = {
        Joints.J1: (-2, 2),
        Joints.J2: (-0.1, 1.46),
        Joints.J3: (-0.95, 1.15),
    }

    def validate_joints(self, joints: List[Joint]) -> None:

        for joint in joints:
            if joint.name in self.valid_ranges:
                vrange = self.valid_ranges[Joints(joint.name)]
                if vrange[0] > joint.value < vrange[1]:
                    raise DobotException(
                        "Value {:.3f} for joint {:s} is out of the range of {:s}.".format(
                            joint.value, joint.name, str(vrange)
                        )
                    )

    def _inverse_kinematics(self, pose: Pose) -> List[Joint]:
        """Computes inverse kinematics.

        Inspired by DobotKinematics.py from open-dobot project and DobotInverseKinematics.py from BenchBot.

        :param pose: IK target pose (relative to robot)
        :return: Inverse kinematics
        """

        self._check_orientation(pose)

        # TODO this is probably not working properly (use similar solution as in _check_orientation?)
        _, _, yaw = quaternion.as_euler_angles(pose.orientation.as_quaternion())

        x = pose.position.x
        y = pose.position.y
        z = pose.position.z + self.end_effector_length

        # pre-compute distances
        # radial position of end effector in the x-y plane
        r = math.sqrt(math.pow(x, 2) + math.pow(y, 2))
        rho_sq = pow(r - self.link_4_length, 2) + pow(z, 2)
        rho = math.sqrt(rho_sq)  # distance b/w the ends of the links joined at the elbow

        l2_sq = self.link_2_length ** 2
        l3_sq = self.link_3_length ** 2

        # law of cosines
        try:
            alpha = math.acos((l2_sq + rho_sq - l3_sq) / (2.0 * self.link_2_length * rho))
            gamma = math.acos((l2_sq + l3_sq - rho_sq) / (2.0 * self.link_2_length * self.link_3_length))
        except ValueError:
            raise DobotException("Failed to compute IK.")

        beta = math.atan2(z, r - self.link_4_length)

        # joint angles
        baseAngle = math.atan2(y, x)
        rearAngle = math.pi / 2 - beta - alpha
        frontAngle = math.pi / 2 - gamma

        joints = [
            Joint(Joints.J1, baseAngle),
            Joint(Joints.J2, rearAngle),
            Joint(Joints.J3, frontAngle),
            Joint(Joints.J4, -rearAngle - frontAngle),
            Joint(Joints.J5, yaw - baseAngle),
        ]
        self.validate_joints(joints)
        return joints

    def inverse_kinematics(
        self,
        end_effector_id: str,
        pose: Pose,
        start_joints: Optional[List[Joint]] = None,
        avoid_collisions: bool = True,
    ) -> List[Joint]:
        """Computes inverse kinematics.

        :param end_effector_id: IK target pose end-effector
        :param pose: IK target pose
        :param start_joints: IK start joints (not supported)
        :param avoid_collisions: Return non-collision IK result if true (not supported)
        :return: Inverse kinematics
        """

        return self._inverse_kinematics(tr.make_pose_rel(self.pose, pose))

    def forward_kinematics(self, end_effector_id: str, joints: List[Joint]) -> Pose:
        """Computes forward kinematics.

        Inspired by DobotKinematics.py from open-dobot project.

        :param end_effector_id: Target end effector name
        :param joints: Input joint values
        :return: Pose of the given end effector
        """

        self.validate_joints(joints)

        j1 = joints[0].value
        j2 = joints[1].value
        j3 = joints[2].value
        sj = j2 + j3

        radius = (
            self.link_2_length * math.cos(j2 - math.pi / 2) + self.link_3_length * math.cos(sj) + self.link_4_length
        )

        x = radius * math.cos(j1)
        y = radius * math.sin(j1)

        z = (
            self.link_2_length * math.cos(j2)
            + self.link_3_length * math.cos(sj + math.pi / 2)
            - self.end_effector_length
        )

        ori = Orientation()
        ori.set_from_quaternion(quaternion.from_euler_angles(0, math.pi, joints[-1].value + j1))

        pose = Pose(Position(x, y, z), ori)

        if __debug__:
            self._check_orientation(pose)

        return tr.make_pose_abs(self.pose, pose)

    def robot_joints(self) -> List[Joint]:

        if self.settings.simulator:
            return self._joint_values

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
