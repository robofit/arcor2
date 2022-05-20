import math

import quaternion

import arcor2.transformations as tr
from arcor2.data.common import Joint, Orientation, Pose, Position, StrEnum
from arcor2_dobot.dobot import Dobot, DobotException
from arcor2_dobot.dobot_api import DobotApiException


class Joints(StrEnum):

    J1: str = "magician_joint_1"
    J2: str = "magician_joint_2"
    J3: str = "magician_joint_3"
    J4: str = "magician_joint_4"
    J5: str = "magician_joint_5"


class DobotMagician(Dobot):

    # Dimensions in meters (according to URDF)
    link_2_length = 0.135
    link_3_length = 0.147
    link_4_length = 0.06
    end_effector_length = 0.06

    def __init__(self, pose: Pose, port: str = "/dev/dobot", simulator: bool = False) -> None:
        super(DobotMagician, self).__init__(pose, port, simulator)

        if self.simulator:
            self._joint_values = [
                Joint(Joints.J1, -0.038),
                Joint(Joints.J2, 0.341),
                Joint(Joints.J3, 0.3632),
                Joint(Joints.J4, -0.704),
                Joint(Joints.J5, -0.568),
            ]

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
    valid_ranges: dict[Joints, tuple[float, float]] = {
        Joints.J1: (-2, 2),
        Joints.J2: (-0.1, 1.46),
        Joints.J3: (-0.95, 1.15),
    }

    def validate_joints(self, joints: list[Joint]) -> None:

        for joint in joints:
            if joint.name in self.valid_ranges:
                vrange = self.valid_ranges[Joints(joint.name)]
                if vrange[0] > joint.value < vrange[1]:
                    raise DobotException(
                        "Value {:.3f} for joint {:s} is out of the range of {:s}.".format(
                            joint.value, joint.name, str(vrange)
                        )
                    )

    def _inverse_kinematics(self, pose: Pose) -> list[Joint]:
        """Computes inverse kinematics.

        Works with robot-relative pose.

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

        l2_sq = self.link_2_length**2
        l3_sq = self.link_3_length**2

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

    def inverse_kinematics(self, pose: Pose) -> list[Joint]:
        """Computes inverse kinematics.

        Works with absolute pose.

        :param end_effector_id: IK target pose end-effector
        :param pose: IK target pose
        :param start_joints: IK start joints (not supported)
        :param avoid_collisions: Return non-collision IK result if true (not supported)
        :return: Inverse kinematics
        """

        return self._inverse_kinematics(tr.make_pose_rel(self.pose, pose))

    def forward_kinematics(self, joints: list[Joint]) -> Pose:
        """Computes forward kinematics.

        Outputs absolute pose.

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

        pose = Pose(
            Position(x, y, z),
            Orientation.from_quaternion(quaternion.from_euler_angles(0, math.pi, joints[-1].value + j1)),
        )

        if __debug__:
            self._check_orientation(pose)

        return tr.make_pose_abs(self.pose, pose)

    def robot_joints(self, include_gripper: bool = False) -> list[Joint]:

        if self.simulator:
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

        if self.simulator:
            return

        try:
            self._dobot.wait_for_cmd(self._dobot.suck(True))
        except DobotApiException as e:
            raise DobotException("Suck failed.") from e

    def release(self) -> None:

        if self.simulator:
            return

        try:
            self._dobot.wait_for_cmd(self._dobot.suck(False))
        except DobotApiException as e:
            raise DobotException("Release failed.") from e
