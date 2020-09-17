from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable, List, Set, TypeVar

from dataclasses_jsonschema import JsonSchemaMixin

from arcor2 import DynamicParamTuple as DPT
from arcor2 import rest
from arcor2.data.common import ActionMetadata, Joint, Orientation, Pose, Position, ProjectRobotJoints, StrEnum
from arcor2.parameter_plugins.relative_pose import RelativePose

from .kinali_abstract_robot import KinaliAbstractRobot

# mypy work-around by GvR (https://github.com/python/mypy/issues/5107#issuecomment-529372406)
if TYPE_CHECKING:
    F = TypeVar("F", bound=Callable)

    def lru_cache(maxsize: int = 128, typed: bool = False) -> Callable[[F], F]:
        pass


else:
    from functools import lru_cache


class MoveTypeEnum(StrEnum):

    LINE: str = "Line"
    SIMPLE: str = "Simple"


@dataclass
class MoveRelativeParameters(JsonSchemaMixin):

    pose: Pose
    position: Position  # relative position
    orientation: Orientation  # relative orientation


@dataclass
class MoveRelativeJointsParameters(JsonSchemaMixin):

    joints: List[Joint]
    position: Position  # relative position
    orientation: Orientation  # relative orientation


class KinaliRobot(KinaliAbstractRobot):
    """REST interface to the robot service (0.7.0)."""

    _ABSTRACT = False

    def move_to_pose(self, end_effector_id: str, target_pose: Pose, speed: float) -> None:
        self.move(end_effector_id, target_pose, MoveTypeEnum.SIMPLE, speed, safe=True)

    def move_to_joints(self, target_joints: List[Joint], speed: float) -> None:
        self.set_joints(ProjectRobotJoints("", "", "", target_joints), MoveTypeEnum.SIMPLE, speed, safe=True)

    # --- EndEffectors Controller --------------------------------------------------------------------------------------

    @lru_cache()
    def get_end_effectors_ids(self) -> Set[str]:
        return set(rest.get_data(f"{self.settings.url}/endEffectors"))

    def get_end_effector_pose(self, end_effector_id: str) -> Pose:
        return rest.get(f"{self.settings.url}/endEffectors/{end_effector_id}/pose", Pose)

    def move(
        self,
        end_effector_id: str,
        pose: Pose,
        move_type: MoveTypeEnum,
        speed: float = 0.5,
        acceleration: float = 0.5,
        safe: bool = True,
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

        if safe:
            url = f"{self.settings.url}/endEffectors/{end_effector_id}/moveCollideLess"
        else:
            url = f"{self.settings.url}/endEffectors/{end_effector_id}/move"

        params = {"moveType": move_type.value, "speed": speed, "acceleration": acceleration}

        with self._move_lock:
            rest.put(url, pose, params)

    def move_relative(
        self,
        end_effector_id: str,
        pose: Pose,
        rel_pose: RelativePose,
        move_type: MoveTypeEnum,
        speed: float = 0.5,
        acceleration: float = 0.5,
        safe: bool = True,
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

        if safe:
            url = f"{self.settings.url}/endEffectors/{end_effector_id}/moveCollideLessRelative"
        else:
            url = f"{self.settings.url}/endEffectors/{end_effector_id}/moveRelative"

        params = {"moveType": move_type.value, "speed": speed, "acceleration": acceleration}
        body = MoveRelativeParameters(pose, rel_pose.position, rel_pose.orientation)

        with self._move_lock:
            rest.put(url, body, params)

    def move_relative_joints(
        self,
        end_effector_id: str,
        joints: ProjectRobotJoints,
        rel_pose: RelativePose,
        move_type: MoveTypeEnum,
        speed: float = 0.5,
        acceleration: float = 0.5,
        safe: bool = True,
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

        if safe:
            url = f"{self.settings.url}/endEffectors/{end_effector_id}/moveJointsCollideLessRelative"
        else:
            url = f"{self.settings.url}/endEffectors/{end_effector_id}/moveJointsRelative"

        body = MoveRelativeJointsParameters(joints.joints, rel_pose.position, rel_pose.orientation)
        params = {"moveType": move_type.value, "speed": speed}

        with self._move_lock:
            rest.put(url, body, params)

    def link(self, end_effector_id: str, collision_id: str) -> None:
        """Links collision object to end effector.

        :param end_effector_id: Unique end-effector id.
        :param collision_id: Unique id of collision
        :return:
        """

        rest.put(f"{self.settings.url}/endEffectors/{end_effector_id}/link", params={"collisionId": collision_id})

    def unlink(self, end_effector_id: str) -> None:
        """Unlinks collision object from end effector.

        :param end_effector_id: Unique end-effector id.
        :return:
        """

        rest.put(f"{self.settings.url}/endEffectors/{end_effector_id}/unlink")

    # --- Grippers Controller ------------------------------------------------------------------------------------------

    @lru_cache()
    def grippers(self) -> Set[str]:
        return set(rest.get_data(f"{self.settings.url}/grippers"))

    def grip(self, gripper_id: str, position: float = 0.0, speed: float = 0.5, force: float = 0.5) -> None:

        assert 0.0 <= position <= 1.0
        assert 0.0 <= speed <= 1.0
        assert 0.0 <= force <= 1.0

        rest.put(
            f"{self.settings.url}/grippers/{gripper_id}/grip",
            params={"position": position, "speed": speed, "force": force},
        )

    def set_opening(self, gripper_id: str, position: float = 1.0, speed: float = 0.5) -> None:

        assert 0.0 <= position <= 1.0
        assert 0.0 <= speed <= 1.0

        rest.put(f"{self.settings.url}/grippers/{gripper_id}/opening", params={"position": position, "speed": speed})

    def get_gripper_opening(self, gripper_id: str) -> float:

        return rest.get_primitive(f"{self.settings.url}/grippers/{gripper_id}/opening", float)

    def is_item_gripped(self, gripper_id: str) -> bool:
        return rest.get_primitive(f"{self.settings.url}/grippers/{gripper_id}/gripped", bool)

    # --- IOs Controller -----------------------------------------------------------------------------------------------

    @lru_cache()
    def inputs(self) -> Set[str]:
        return set(rest.get_data(f"{self.settings.url}/inputs"))

    @lru_cache()
    def outputs(self) -> Set[str]:
        return set(rest.get_data(f"{self.settings.url}/outputs"))

    def get_input(self, input_id: str) -> float:
        return rest.get_primitive(f"{self.settings.url}/inputs/{input_id}", float)

    def set_output(self, output_id: str, value: float) -> None:

        assert 0.0 <= value <= 1.0
        rest.put(f"{self.settings.url}/outputs/{output_id}", params={"value": value})

    def get_output(self, output_id: str) -> float:
        return rest.get_primitive(f"{self.settings.url}/outputs/{output_id}", float)

    # --- Joints Controller --------------------------------------------------------------------------------------------

    def set_joints(
        self,
        joints: ProjectRobotJoints,
        move_type: MoveTypeEnum,
        speed: float = 0.5,
        acceleration: float = 0.5,
        safe: bool = True,
    ) -> None:

        assert 0.0 <= speed <= 1.0
        assert 0.0 <= acceleration <= 1.0

        if safe:
            url = f"{self.settings.url}/jointsCollideLess"
        else:
            url = f"{self.settings.url}/joints"

        params = {"moveType": move_type.value, "speed": speed, "acceleration": acceleration}

        with self._move_lock:
            rest.put(url, joints.joints, params)

    def robot_joints(self) -> List[Joint]:
        return rest.get_list(f"{self.settings.url}/joints", Joint)

    # --- Robot Controller ---------------------------------------------------------------------------------------------

    @lru_cache()
    def moves(self) -> Set[str]:
        return set(rest.get_list_primitive(f"{self.settings.url}/moves", str))

    def stop(self) -> None:
        rest.put(f"{self.settings.url}/stop")

    # --- Suctions Controller ------------------------------------------------------------------------------------------

    @lru_cache()
    def suctions(self) -> Set[str]:
        return set(rest.get_data(f"{self.settings.url}/suctions"))

    def suck(self, suction_id: str) -> None:
        rest.put(f"{self.settings.url}/suctions/{suction_id}/suck")

    def release(self, suction_id: str) -> None:
        rest.put(f"{self.settings.url}/suctions/{suction_id}/release")

    def is_item_attached(self, suction_id: str) -> bool:
        return rest.get_primitive(f"{self.settings.url}/suctions/{suction_id}/attached", bool)

    move.__action__ = ActionMetadata(blocking=True)  # type: ignore
    move_relative.__action__ = ActionMetadata(blocking=True)  # type: ignore
    move_relative_joints.__action__ = ActionMetadata(blocking=True)  # type: ignore
    set_joints.__action__ = ActionMetadata(blocking=True)  # type: ignore
    get_input.__action__ = ActionMetadata(blocking=True)  # type: ignore
    set_output.__action__ = ActionMetadata(blocking=True)  # type: ignore
    get_output.__action__ = ActionMetadata(blocking=True)  # type: ignore
    grip.__action__ = ActionMetadata(blocking=True)  # type: ignore
    set_opening.__action__ = ActionMetadata(blocking=True)  # type: ignore
    get_gripper_opening.__action__ = ActionMetadata(blocking=True)  # type: ignore
    is_item_gripped.__action__ = ActionMetadata(blocking=True)  # type: ignore
    suck.__action__ = ActionMetadata(blocking=True)  # type: ignore
    release.__action__ = ActionMetadata(blocking=True)  # type: ignore
    is_item_attached.__action__ = ActionMetadata(blocking=True)  # type: ignore


KinaliRobot.DYNAMIC_PARAMS = {
    "end_effector_id": DPT(KinaliRobot.get_end_effectors_ids.__name__, set()),
    "gripper_id": DPT(KinaliRobot.grippers.__name__, set()),
    "suction_id": DPT(KinaliRobot.suctions.__name__, set()),
    "input_id": DPT(KinaliRobot.inputs.__name__, set()),
    "output_id": DPT(KinaliRobot.outputs.__name__, set()),
}

KinaliRobot.CANCEL_MAPPING = {
    KinaliRobot.move.__name__: KinaliRobot.stop.__name__,
    KinaliRobot.move_relative.__name__: KinaliRobot.stop.__name__,
    KinaliRobot.move_relative_joints.__name__: KinaliRobot.stop.__name__,
    KinaliRobot.set_joints.__name__: KinaliRobot.stop.__name__,
}
