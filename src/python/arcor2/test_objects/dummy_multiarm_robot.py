import time

from arcor2 import transformations as tr
from arcor2.data.common import Joint, Pose, StrEnum
from arcor2.exceptions import Arcor2Exception
from arcor2.object_types.abstract import MultiArmRobot, Settings


class DummyMultiArmRobot(MultiArmRobot):
    """Example class representing multiarm robot."""

    _ABSTRACT = False

    class Arms(StrEnum):
        left: str = "left"
        right: str = "right"

    GRIPPERS: dict[str, set[str]] = {
        Arms.left: {"l_gripper_1", "l_gripper_2"},
        Arms.right: {"r_gripper_1", "r_gripper_2"},
    }
    SUCTIONS: dict[str, set[str]] = {
        Arms.left: {"l_suction_1", "l_suction_2"},
        Arms.right: {"r_suction_1", "r_suction_2"},
    }
    EEF: dict[str, set[str]] = {Arms.left: {"l_eef_1", "l_eef_2"}, Arms.right: {"r_eef_1", "r_eef_2"}}

    JOINTS: dict[str, list[Joint]] = {Arms.left: [Joint("l_joint_1", 1.0)], Arms.right: [Joint("r_joint_1", -1.0)]}

    def __init__(self, obj_id: str, name: str, pose: Pose, settings: None | Settings = None) -> None:
        super().__init__(obj_id, name, pose, settings)

        self._hand_teaching: dict[str, bool] = {self.Arms.left: False, self.Arms.right: False}
        self._poses: dict[str, dict[str, Pose]] = {}

        for arm, eefs in self.EEF.items():
            self._poses[arm] = {}
            for eef in eefs:
                self._poses[arm][eef] = Pose()

    def get_arm_ids(self) -> set[str]:
        return self.Arms.set()

    @staticmethod
    def _get_from_dict(d: dict[str, set[str]], arm_id: None | str = None) -> set[str]:

        if arm_id is None:
            raise Arcor2Exception("Arm has to be specified.")

        try:
            return d[arm_id]
        except KeyError:
            raise Arcor2Exception("Unknown arm.")

    def get_end_effectors_ids(self, arm_id: None | str = None) -> set[str]:
        return self._get_from_dict(self.EEF, arm_id)

    def get_end_effector_pose(self, end_effector: str, arm_id: None | str = None) -> Pose:

        if end_effector not in self.get_end_effectors_ids(arm_id):
            raise Arcor2Exception("Unknown end effector.")

        assert arm_id

        return tr.make_pose_abs(self.pose, self._poses[arm_id][end_effector])

    def robot_joints(self, include_gripper: bool = False, arm_id: None | str = None) -> list[Joint]:
        """With no arm specified, returns all robot joints. Otherwise, returns
        joints for the given arm.

        :param arm_id:
        :return:
        """

        if arm_id is None:
            return [item for sublist in self.JOINTS.values() for item in sublist]

        try:
            return self.JOINTS[arm_id]
        except KeyError:
            raise Arcor2Exception("Unknown arm.")

    def grippers(self, arm_id: None | str = None) -> set[str]:
        return self._get_from_dict(self.GRIPPERS, arm_id)

    def suctions(self, arm_id: None | str = None) -> set[str]:
        return self._get_from_dict(self.SUCTIONS, arm_id)

    def move_to_pose(
        self,
        end_effector_id: str,
        target_pose: Pose,
        speed: float,
        safe: bool = True,
        linear: bool = True,
        arm_id: None | str = None,
    ) -> None:
        """Move given robot's end effector to the selected pose.

        :param end_effector_id:
        :param target_pose:
        :param speed:
        :param safe:
        :return:
        """

        if end_effector_id not in self.get_end_effectors_ids(arm_id):
            raise Arcor2Exception("Unknown end effector.")

        assert arm_id

        speed = min(max(0.0, speed), 1.0)

        with self._move_lock:
            time.sleep(1.0 - speed)
            self._poses[arm_id][end_effector_id] = tr.make_pose_rel(self.pose, target_pose)

    def move_to_joints(
        self, target_joints: list[Joint], speed: float, safe: bool = True, arm_id: None | str = None
    ) -> None:
        """Sets target joint values.

        :param target_joints:
        :param speed:
        :param safe:
        :return:
        """

        if arm_id is None:
            if len(target_joints) != len(self.robot_joints()):
                raise Arcor2Exception("Joints for both arms have to be specified.")
        elif arm_id not in self.get_arm_ids():
            raise Arcor2Exception("Unknown arm.")

        speed = min(max(0.0, speed), 1.0)

        with self._move_lock:
            time.sleep(1.0 - speed)

    def inverse_kinematics(
        self,
        end_effector_id: str,
        pose: Pose,
        start_joints: None | list[Joint] = None,
        avoid_collisions: bool = True,
        arm_id: None | str = None,
    ) -> list[Joint]:
        """Computes inverse kinematics.

        :param end_effector_id: IK target pose end-effector
        :param pose: IK target pose
        :param start_joints: IK start joints
        :param avoid_collisions: Return non-collision IK result if true
        :return: Inverse kinematics
        """

        if end_effector_id not in self.get_end_effectors_ids(arm_id):
            raise Arcor2Exception("Unknown end effector.")

        assert arm_id is not None

        try:
            return self.JOINTS[arm_id]
        except KeyError:
            raise Arcor2Exception("Unknown arm.")

    def forward_kinematics(self, end_effector_id: str, joints: list[Joint], arm_id: None | str = None) -> Pose:
        """Computes forward kinematics.

        :param end_effector_id: Target end effector name
        :param joints: Input joint values
        :return: Pose of the given end effector
        """

        if end_effector_id not in self.get_end_effectors_ids(arm_id):
            raise Arcor2Exception("Unknown end effector.")

        return Pose()

    def get_hand_teaching_mode(self, arm_id: None | str = None) -> bool:
        """
        This is expected to be implemented if the robot supports set_hand_teaching_mode
        :return:
        """

        if arm_id is None:
            raise Arcor2Exception("Arm has to be specified.")

        try:
            return self._hand_teaching[arm_id]
        except KeyError:
            raise Arcor2Exception("Unknown arm.")

    def set_hand_teaching_mode(self, enabled: bool, arm_id: None | str = None) -> None:

        if arm_id is None:
            raise Arcor2Exception("Arm has to be specified.")

        try:
            state = self._hand_teaching[arm_id]
        except KeyError:
            raise Arcor2Exception("Unknown arm.")

        if state == enabled:
            raise Arcor2Exception("That's the current state.")

        self._hand_teaching[arm_id] = enabled
