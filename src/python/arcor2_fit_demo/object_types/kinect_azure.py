from dataclasses import dataclass
from io import BytesIO
from typing import Optional, cast

from PIL import Image

from arcor2 import rest
from arcor2.data.camera import CameraParameters
from arcor2.data.common import ActionMetadata, Pose
from arcor2.data.object_type import Models
from arcor2.object_types.abstract import Camera
from arcor2.object_types.abstract import Settings as BaseSettings


@dataclass
class Settings(BaseSettings):
    url: str


class KinectAzure(Camera):

    _ABSTRACT = False

    def __init__(
        self,
        obj_id: str,
        name: str,
        pose: Pose,
        collision_model: Optional[Models] = None,
        settings: Optional[Settings] = None,
    ) -> None:

        super(KinectAzure, self).__init__(obj_id, name, pose, collision_model, settings)

        if self._started():
            self._stop()

        self._start()  # TODO start with user-set parameters
        self.color_camera_params = rest.call(
            rest.Method.GET, f"{self.settings.url}/color/parameters", return_type=CameraParameters
        )

    @property
    def settings(self) -> Settings:
        return cast(Settings, super(KinectAzure, self).settings)

    def _start(self) -> None:
        rest.call(rest.Method.PUT, f"{self.settings.url}/state/start")

    def _started(self) -> bool:
        return rest.call(rest.Method.GET, f"{self.settings.url}/state/started", return_type=bool)

    def _stop(self) -> None:
        rest.call(rest.Method.PUT, f"{self.settings.url}/state/stop")

    def color_image(self, *, an: Optional[str] = None) -> Image.Image:
        return rest.get_image(f"{self.settings.url}/color/image")

    def depth_image(self, averaged_frames: int = 1, *, an: Optional[str] = None) -> Image.Image:
        return Image.open(
            rest.call(
                rest.Method.GET,
                f"{self.settings.url}/depth/image",
                return_type=BytesIO,
                params={"averagedFrames": averaged_frames},
            )
        )

    def sync_images(self) -> None:
        pass

    def cleanup(self) -> None:

        super(KinectAzure, self).cleanup()
        self._stop()

    color_image.__action__ = ActionMetadata(blocking=True)  # type: ignore
    # depth_image.__action__ = ActionMetadata(blocking=True)  # type: ignore
