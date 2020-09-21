from dataclasses import dataclass
from typing import Set, cast

from arcor2 import rest
from arcor2.data.common import Pose
from arcor2.object_types.abstract import Robot, Settings


@dataclass
class KinaliRobotSettings(Settings):
    url: str
    configuration_id: str


class KinaliAbstractRobot(Robot):
    """Object (with pose) that server as a base for Robot service.

    In future, there might be two objects like this: one for robots with
    end effectors (Aubo) and one for robots without end effectors
    (simatic).
    """

    def __init__(self, obj_id: str, name: str, pose: Pose, settings: KinaliRobotSettings) -> None:
        super(KinaliAbstractRobot, self).__init__(obj_id, name, pose, settings)
        rest.put(
            f"{self.settings.url}/system/set", pose, params={"configId": self.settings.configuration_id, "id": self.id}
        )

    @property
    def settings(self) -> KinaliRobotSettings:
        return cast(KinaliRobotSettings, super(KinaliAbstractRobot, self).settings)

    def configurations(self) -> Set[str]:
        return set(rest.get_list_primitive(f"{self.settings.url}/configurations", str))

    def cleanup(self) -> None:
        super(KinaliAbstractRobot, self).cleanup()
        rest.put(f"{self.settings.url}/system/reset")


__all__ = [KinaliRobotSettings.__name__, KinaliAbstractRobot.__name__]
