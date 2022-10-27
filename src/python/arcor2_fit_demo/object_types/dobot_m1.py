from dataclasses import dataclass

from arcor2 import rest
from arcor2.data.common import Pose

from .abstract_dobot import AbstractDobot  # noqa:ABS101
from .fit_common_mixin import UrlSettings  # noqa:ABS101


@dataclass
class M1Settings(UrlSettings):

    url: str = "http://fit-demo-dobot-m1:5018"


class DobotM1(AbstractDobot):

    _ABSTRACT = False
    urdf_package_name = "dobot-m1.zip"

    def __init__(self, obj_id: str, name: str, pose: Pose, settings: M1Settings) -> None:
        super().__init__(obj_id, name, pose, settings)
        self._start()

    def get_hand_teaching_mode(self) -> bool:
        return rest.call(rest.Method.GET, f"{self.settings.url}/hand_teaching", return_type=bool)

    def set_hand_teaching_mode(self, enabled: bool) -> None:
        rest.call(rest.Method.PUT, f"{self.settings.url}/hand_teaching", params={"enabled": enabled})
