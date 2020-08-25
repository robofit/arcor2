from dataclasses import dataclass
from typing import cast

from arcor2 import rest
from arcor2.data.common import Pose
from arcor2.object_types.abstract import Robot, Settings


@dataclass
class KinaliRobotSettings(Settings):
    url: str
    robot_id: str


class KinaliAbstractRobot(Robot):
    """Object (with pose) that server as a base for Robot service.

    In future, there might be two objects like this: one for robots with
    end effectors (Aubo) and one for robots without end effectors
    (simatic).
    """

    def __init__(self, obj_id: str, name: str, pose: Pose, settings: KinaliRobotSettings) -> None:
        super(KinaliAbstractRobot, self).__init__(obj_id, name, pose, settings)
        self._create()

    @property
    def settings(self) -> KinaliRobotSettings:
        return cast(KinaliRobotSettings, super(KinaliAbstractRobot, self).settings)

    def _robot_id(self) -> str:
        return rest.get_primitive(f"{self.settings.url}/systems/robotId", str)

    def _create(self):
        # if self._robot_id() != self.settings.robot_id:
        rest.put(f"{self.settings.url}/systems/robotId", params={"robot_id": self.settings.robot_id})


__all__ = [KinaliRobotSettings.__name__, KinaliAbstractRobot.__name__]
