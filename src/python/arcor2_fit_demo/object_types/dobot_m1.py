from arcor2.data.common import Pose

from .abstract_dobot import AbstractDobot, DobotSettings


class DobotM1(AbstractDobot):

    _ABSTRACT = False
    urdf_package_name = "dobot-m1.zip"

    def __init__(self, obj_id: str, name: str, pose: Pose, settings: DobotSettings) -> None:
        super(DobotM1, self).__init__(obj_id, name, pose, settings)
        self._start("m1")
