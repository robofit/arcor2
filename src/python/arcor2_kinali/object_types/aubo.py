from dataclasses import dataclass
from typing import List, Optional, Set

from dataclasses_jsonschema import JsonSchemaMixin

from arcor2 import DynamicParamTuple as DPT
from arcor2 import rest
from arcor2.data.common import ActionMetadata, Joint, Orientation, Pose, Position, ProjectRobotJoints, RelativePose

from .abstract_robot import AbstractRobot, MoveTypeEnum, lru_cache


@dataclass
class MoveRelativeParameters(JsonSchemaMixin):

    pose: Pose
    position: Position
    orientation: Orientation


@dataclass
class MoveRelativeJointsParameters(JsonSchemaMixin):

    joints: List[Joint]
    position: Position
    orientation: Orientation


class Aubo(AbstractRobot):
    """REST interface to the robot service (0.7.0)."""

    _ABSTRACT = False
    urdf_package_name = "aubo.zip"

    def move_to_pose(self, end_effector_id: str, target_pose: Pose, speed: float, safe: bool = True) -> None:
        self.move(end_effector_id, target_pose, MoveTypeEnum.SIMPLE, speed, safe=safe)

    # --- EndEffectors Controller --------------------------------------------------------------------------------------

    @lru_cache()
    def get_end_effectors_ids(self) -> Set[str]:
        return set(rest.call(rest.Method.GET, f"{self.settings.url}/endEffectors", list_return_type=str))

    def get_end_effector_pose(self, end_effector_id: str) -> Pose:
        return rest.call(rest.Method.GET, f"{self.settings.url}/endEffectors/{end_effector_id}/pose", return_type=Pose)

    def move(
        self,
        end_effector_id: str,
        pose: Pose,
        move_type: MoveTypeEnum,
        speed: float = 0.5,
        acceleration: float = 0.5,
        safe: bool = True,
        *,
        an: Optional[str] = None,
    ) -> None:
        """Moves the robot's end-effector to a specific pose.

        :param end_effector_id: Unique end-effector id.
        :param pose: Target pose.
        :param move_type: Type of move.
        :param speed: Speed of move.
        :param acceleration: Acceleration of move.
        :param safe: When true, robot will consider its environment and avoid collisions.
        :return:
        """

        assert 0.0 <= speed <= 1.0
        assert 0.0 <= acceleration <= 1.0

        url = f"{self.settings.url}/endEffectors/{end_effector_id}/move"

        params = {"moveType": move_type.value, "speed": speed, "acceleration": acceleration, "safe": safe}

        with self._move_lock:
            rest.call(rest.Method.PUT, url, body=pose, params=params, timeout=self.move_timeout)

    def move_relative(
        self,
        end_effector_id: str,
        pose: Pose,
        rel_pose: RelativePose,
        move_type: MoveTypeEnum,
        speed: float = 0.5,
        acceleration: float = 0.5,
        safe: bool = True,
        *,
        an: Optional[str] = None,
    ) -> None:
        """Moves the robot's end-effector to a specific pose.

        :param end_effector_id: Unique end-effector id.
        :param pose: Target pose.
        :param rel_pose: Relative pose.
        :param move_type: Type of move.
        :param speed: Speed of move.
        :param acceleration: Acceleration of move.
        :param safe: When true, robot will consider its environment and avoid collisions.
        :return:
        """

        assert 0.0 <= speed <= 1.0
        assert 0.0 <= acceleration <= 1.0

        url = f"{self.settings.url}/endEffectors/{end_effector_id}/moveRelative"

        params = {"moveType": move_type.value, "speed": speed, "acceleration": acceleration, "safe": safe}
        body = MoveRelativeParameters(pose, rel_pose.position, rel_pose.orientation)

        with self._move_lock:
            rest.call(rest.Method.PUT, url, body=body, params=params, timeout=self.move_timeout)

    def move_relative_joints(
        self,
        end_effector_id: str,
        joints: ProjectRobotJoints,
        rel_pose: RelativePose,
        move_type: MoveTypeEnum,
        speed: float = 0.5,
        acceleration: float = 0.5,
        safe: bool = True,
        *,
        an: Optional[str] = None,
    ) -> None:
        """Moves the robot's end-effector relatively to specific joint values.

        :param robot_id: Unique robot id.
        :param end_effector_id: Unique end-effector id.
        :param joints: Target joints.
        :param rel_pose: Relative pose.
        :param move_type: Type of move.
        :param speed: Speed of move.
        :param acceleration: Acceleration of move.
        :param safe: When true, robot will consider its environment and avoid collisions.
        :return:
        """

        assert 0.0 <= speed <= 1.0
        assert 0.0 <= acceleration <= 1.0

        url = f"{self.settings.url}/endEffectors/{end_effector_id}/moveJointsRelative"

        body = MoveRelativeJointsParameters(joints.joints, rel_pose.position, rel_pose.orientation)
        params = {"moveType": move_type.value, "speed": speed, "acceleration": acceleration, "safe": safe}

        with self._move_lock:
            rest.call(rest.Method.PUT, url, body=body, params=params, timeout=self.move_timeout)

    def link(self, end_effector_id: str, collision_id: str) -> None:
        """Links collision object to end effector.

        :param end_effector_id: Unique end-effector id.
        :param collision_id: Unique id of collision
        :return:
        """

        rest.call(
            rest.Method.PUT,
            f"{self.settings.url}/endEffectors/{end_effector_id}/link",
            params={"collisionId": collision_id},
        )

    def unlink(self, end_effector_id: str) -> None:
        """Unlinks collision object from end effector.

        :param end_effector_id: Unique end-effector id.
        :return:
        """

        rest.call(rest.Method.PUT, f"{self.settings.url}/endEffectors/{end_effector_id}/unlink")

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
        :param start_joints: IK start joints (if not provided, current joint values will be used)
        :param avoid_collisions: Return non-collision IK result if true
        :return: Inverse kinematics
        """

        if start_joints is None:
            start_joints = self.robot_joints()

        return rest.call(
            rest.Method.PUT,
            f"{self.settings.url}/endEffectors/{end_effector_id}/inverseKinematics",
            params={"startJoints": [joint.to_dict() for joint in start_joints], "avoidCollisions": avoid_collisions},
            body=pose,
            list_return_type=Joint,
        )

    def forward_kinematics(self, end_effector_id: str, joints: List[Joint]) -> Pose:
        """Computes forward kinematics.

        :param end_effector_id: Target end effector name
        :param joints: Input joint values
        :return: Pose of the given end effector
        """
        return rest.call(
            rest.Method.PUT,
            f"{self.settings.url}/endEffectors/{end_effector_id}/forwardKinematics",
            body=joints,
            return_type=Pose,
        )

    # --- Suctions Controller ------------------------------------------------------------------------------------------

    @lru_cache()
    def suctions(self) -> Set[str]:
        return set(rest.call(rest.Method.GET, f"{self.settings.url}/suctions", list_return_type=str))

    def suck(self, suction_id: str, *, an: Optional[str] = None) -> None:
        rest.call(rest.Method.PUT, f"{self.settings.url}/suctions/{suction_id}/suck")

    def release(self, suction_id: str, *, an: Optional[str] = None) -> None:
        rest.call(rest.Method.PUT, f"{self.settings.url}/suctions/{suction_id}/release")

    def is_item_attached(self, suction_id: str, *, an: Optional[str] = None) -> bool:
        return rest.call(rest.Method.GET, f"{self.settings.url}/suctions/{suction_id}/attached", return_type=bool)

    move.__action__ = ActionMetadata(blocking=True)  # type: ignore
    move_relative.__action__ = ActionMetadata(blocking=True)  # type: ignore
    move_relative_joints.__action__ = ActionMetadata(blocking=True)  # type: ignore
    suck.__action__ = ActionMetadata(blocking=True)  # type: ignore
    release.__action__ = ActionMetadata(blocking=True)  # type: ignore
    is_item_attached.__action__ = ActionMetadata(blocking=True)  # type: ignore


Aubo.DYNAMIC_PARAMS = {
    "end_effector_id": DPT(Aubo.get_end_effectors_ids.__name__, set()),
    "gripper_id": DPT(Aubo.grippers.__name__, set()),
    "suction_id": DPT(Aubo.suctions.__name__, set()),
    "input_id": DPT(Aubo.inputs.__name__, set()),
    "output_id": DPT(Aubo.outputs.__name__, set()),
}

Aubo.CANCEL_MAPPING.update(
    {
        Aubo.move.__name__: Aubo.stop.__name__,
        Aubo.move_relative.__name__: Aubo.stop.__name__,
        Aubo.move_relative_joints.__name__: Aubo.stop.__name__,
    }
)
