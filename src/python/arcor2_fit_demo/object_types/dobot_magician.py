import math
from typing import Dict, List, Optional, Tuple

import quaternion  # type: ignore
from pydobot import dobot  # type: ignore

import arcor2.transformations as tr
from arcor2.data.common import ActionMetadata, Joint, Orientation, Pose, Position, StrEnum

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

    # Dimentions in meters (according to URDF)
    link_2_length = 0.135
    link_3_length = 0.147
    link_4_length = 0.06
    end_effector_length = 0.06

    def get_end_effector_pose(self, end_effector_id: str) -> Pose:

        pose = super(DobotMagician, self).get_end_effector_pose(end_effector_id)

        if self.settings.simulator:
            return pose

        base_joint = self.robot_joints()[0].value

        pose.position.x += self.link_4_length * math.cos(base_joint)
        pose.position.y += self.link_4_length * math.sin(base_joint)
        pose.position.z -= self.end_effector_length

        return pose

    valid_ranges: Dict[Joints, Tuple[float, float]] = {
        Joints.J1: (-2, 2),
        Joints.J2: (0, 1.46),
        Joints.J3: (0.69, 2.47),  # TODO joint4/5
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

    def inverse_kinematics(
        self,
        end_effector_id: str,
        pose: Pose,
        start_joints: Optional[List[Joint]] = None,
        avoid_collisions: bool = True,
    ) -> List[Joint]:
        """Computes inverse kinematics.

        Inspired by DobotKinematics.py from open-dobot project and DobotInverseKinematics.py from BenchBot.

        :param end_effector_id: IK target pose end-effector
        :param pose: IK target pose
        :param start_joints: IK start joints (not supported)
        :param avoid_collisions: Return non-collision IK result if true (not supported)
        :return: Inverse kinematics
        """

        local_pose = tr.make_pose_rel(self.pose, pose)

        x = local_pose.position.x
        y = local_pose.position.y
        z = local_pose.position.z + self.end_effector_length

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
        frontAngle = math.pi - gamma
        j5 = quaternion.as_euler_angles(pose.orientation.as_quaternion())[2]

        joints = [
            Joint(Joints.J1, baseAngle),
            Joint(Joints.J2, rearAngle),
            Joint(Joints.J3, frontAngle),
            Joint(Joints.J4, math.pi / 2 - rearAngle - frontAngle),
            Joint(Joints.J5, j5),
        ]
        self.validate_joints(joints)
        return joints

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
            self.link_2_length * math.cos(j2 - math.pi / 2)
            + self.link_3_length * math.cos(sj - math.pi / 2)
            + self.link_4_length
        )

        x = radius * math.cos(j1)
        y = radius * math.sin(j1)

        z = self.link_2_length * math.cos(j2) + self.link_3_length * math.cos(sj) - self.end_effector_length

        ori = Orientation()
        ori.set_from_quaternion(quaternion.from_euler_angles(0, math.pi, joints[-1].value))
        return tr.make_pose_abs(self.pose, Pose(Position(x, y, z), ori))

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
            Joint(Joints.J3, joints.j3 - joints.j2 + math.pi / 2),
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
