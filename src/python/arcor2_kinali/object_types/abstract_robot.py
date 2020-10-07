from dataclasses import dataclass
from typing import Set, cast

from arcor2 import rest
from arcor2.data.common import Pose
from arcor2.object_types.abstract import Robot
from arcor2.object_types.abstract import Settings as BaseSettings


@dataclass
class Settings(BaseSettings):
    url: str
    configuration_id: str


class AbstractRobot(Robot):
    """Object (with pose) that serves as a base for Robot service.

    In future, there might be two objects like this: one for robots with
    end effectors (Aubo) and one for robots without end effectors
    (simatic).
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


__all__ = [Settings.__name__, AbstractRobot.__name__]
