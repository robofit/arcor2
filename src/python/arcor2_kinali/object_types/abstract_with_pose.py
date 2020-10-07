from dataclasses import dataclass
from typing import Optional, cast

from arcor2 import rest
from arcor2.data.common import Pose
from arcor2.data.object_type import Models
from arcor2.object_types.abstract import GenericWithPose
from arcor2.object_types.abstract import Settings as BaseSettings


@dataclass
class Settings(BaseSettings):
    url: str
    configuration_id: str


class AbstractWithPose(GenericWithPose):
    """Object (without pose) that serves as a base class for feature services
    with 'Configurations' and 'System' controller."""

    def __init__(
        self,
        obj_id: str,
        name: str,
        pose: Pose,
        collision_model: Optional[Models] = None,
        settings: Optional[Settings] = None,
    ) -> None:
        super(AbstractWithPose, self).__init__(obj_id, name, pose, collision_model, settings)
        rest.call(
            rest.Method.PUT,
            f"{self.settings.url}/system/set",
            body=pose,
            params={"configId": self.settings.configuration_id, "id": self.id},
        )

    @property
    def settings(self) -> Settings:
        return cast(Settings, super(AbstractWithPose, self).settings)

    def cleanup(self) -> None:
        super(AbstractWithPose, self).cleanup()
        rest.call(rest.Method.PUT, f"{self.settings.url}/system/reset")


__all__ = [
    Settings.__name__,
    AbstractWithPose.__name__,
]
