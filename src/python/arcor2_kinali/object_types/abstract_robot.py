from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable, List, Optional, Set, TypeVar, cast

from arcor2 import rest
from arcor2.data.common import ActionMetadata, Joint, Pose, ProjectRobotJoints, StrEnum
from arcor2.object_types.abstract import Robot
from arcor2.object_types.abstract import Settings as BaseSettings


@dataclass
class Settings(BaseSettings):
    url: str
    configuration_id: str


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


class AbstractRobot(Robot):
    """Object (with pose) that serves as a base for Robot service.

    There are methods/action that are common to robots with (Aubo) and
    without (Simatic) end effectors.
    """

    def __init__(self, obj_id: str, name: str, pose: Pose, settings: Settings) -> None:
        super(AbstractRobot, self).__init__(obj_id, name, pose, settings)
        rest.call(
            rest.Method.PUT,
            f"{self.settings.url}/system/set",
            body=pose,
            params={"configId": self.settings.configuration_id, "id": self.id},
        )

        self.move_timeout = rest.Timeout(read=5 * 60)

    @property
    def settings(self) -> Settings:
        return cast(Settings, super(AbstractRobot, self).settings)

    def configurations(self) -> Set[str]:
        return set(rest.call(rest.Method.GET, f"{self.settings.url}/configurations", list_return_type=str))

    def cleanup(self) -> None:
        super(AbstractRobot, self).cleanup()
        rest.call(rest.Method.PUT, f"{self.settings.url}/system/reset")

    def move_to_joints(self, target_joints: List[Joint], speed: float, safe: bool = True) -> None:
        self.set_joints(ProjectRobotJoints("", "", target_joints), MoveTypeEnum.SIMPLE, speed, safe=safe)

    # --- Grippers Controller ------------------------------------------------------------------------------------------

    @lru_cache()
    def grippers(self) -> Set[str]:
        return set(rest.call(rest.Method.GET, f"{self.settings.url}/grippers", list_return_type=str))

    def grip(
        self,
        gripper_id: str,
        position: float = 0.0,
        speed: float = 0.5,
        force: float = 0.5,
        *,
        an: Optional[str] = None,
    ) -> None:

        assert 0.0 <= position <= 1.0
        assert 0.0 <= speed <= 1.0
        assert 0.0 <= force <= 1.0

        rest.call(
            rest.Method.PUT,
            f"{self.settings.url}/grippers/{gripper_id}/grip",
            params={"position": position, "speed": speed, "force": force},
        )

    def set_opening(
        self, gripper_id: str, position: float = 1.0, speed: float = 0.5, *, an: Optional[str] = None
    ) -> None:

        assert 0.0 <= position <= 1.0
        assert 0.0 <= speed <= 1.0

        rest.call(
            rest.Method.PUT,
            f"{self.settings.url}/grippers/{gripper_id}/opening",
            params={"position": position, "speed": speed},
        )

    def get_gripper_opening(self, gripper_id: str, *, an: Optional[str] = None) -> float:

        return rest.call(rest.Method.GET, f"{self.settings.url}/grippers/{gripper_id}/opening", return_type=float)

    def is_item_gripped(self, gripper_id: str, *, an: Optional[str] = None) -> bool:
        return rest.call(rest.Method.GET, f"{self.settings.url}/grippers/{gripper_id}/gripped", return_type=bool)

    # --- IOs Controller -----------------------------------------------------------------------------------------------

    @lru_cache()
    def inputs(self) -> Set[str]:
        return set(rest.call(rest.Method.GET, f"{self.settings.url}/inputs", return_type=str))

    @lru_cache()
    def outputs(self) -> Set[str]:
        return set(rest.call(rest.Method.GET, f"{self.settings.url}/outputs", return_type=str))

    def get_input(self, input_id: str, *, an: Optional[str] = None) -> float:
        return rest.call(rest.Method.GET, f"{self.settings.url}/inputs/{input_id}", return_type=float)

    def set_output(self, output_id: str, value: float, *, an: Optional[str] = None) -> None:

        assert 0.0 <= value <= 1.0
        rest.call(rest.Method.PUT, f"{self.settings.url}/outputs/{output_id}", params={"value": value})

    def get_output(self, output_id: str, *, an: Optional[str] = None) -> float:
        return rest.call(rest.Method.GET, f"{self.settings.url}/outputs/{output_id}", return_type=float)

    # --- Joints Controller --------------------------------------------------------------------------------------------

    def set_joints(
        self,
        joints: ProjectRobotJoints,
        move_type: MoveTypeEnum,
        speed: float = 0.5,
        acceleration: float = 0.5,
        safe: bool = True,
        *,
        an: Optional[str] = None,
    ) -> None:

        assert 0.0 <= speed <= 1.0
        assert 0.0 <= acceleration <= 1.0

        url = f"{self.settings.url}/joints"
        params = {"moveType": move_type.value, "speed": speed, "acceleration": acceleration, "safe": safe}

        with self._move_lock:
            rest.call(rest.Method.PUT, url, body=joints.joints, params=params, timeout=self.move_timeout)

    def robot_joints(self) -> List[Joint]:
        return rest.call(rest.Method.GET, f"{self.settings.url}/joints", list_return_type=Joint)

    # --- Robot Controller ---------------------------------------------------------------------------------------------

    @lru_cache()
    def moves(self) -> Set[str]:
        return set(rest.call(rest.Method.GET, f"{self.settings.url}/moves", list_return_type=str))

    def stop(self) -> None:
        rest.call(rest.Method.PUT, f"{self.settings.url}/stop")

    set_joints.__action__ = ActionMetadata(blocking=True)  # type: ignore
    get_input.__action__ = ActionMetadata(blocking=True)  # type: ignore
    set_output.__action__ = ActionMetadata(blocking=True)  # type: ignore
    get_output.__action__ = ActionMetadata(blocking=True)  # type: ignore
    grip.__action__ = ActionMetadata(blocking=True)  # type: ignore
    set_opening.__action__ = ActionMetadata(blocking=True)  # type: ignore
    get_gripper_opening.__action__ = ActionMetadata(blocking=True)  # type: ignore
    is_item_gripped.__action__ = ActionMetadata(blocking=True)  # type: ignore


AbstractRobot.CANCEL_MAPPING = {
    AbstractRobot.set_joints.__name__: AbstractRobot.stop.__name__,
}


__all__ = [Settings.__name__, AbstractRobot.__name__]
