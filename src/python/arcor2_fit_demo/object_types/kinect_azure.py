from io import BytesIO

from PIL import Image

from arcor2 import rest
from arcor2.data.camera import CameraParameters
from arcor2.data.common import ActionMetadata, Pose
from arcor2.data.object_type import Models
from arcor2.object_types.abstract import Camera

from .fit_common_mixin import FitCommonMixin, UrlSettings  # noqa:ABS101


class KinectAzure(FitCommonMixin, Camera):

    _ABSTRACT = False
    mesh_filename = "kinect_azure.dae"

    def __init__(
        self,
        obj_id: str,
        name: str,
        pose: Pose,
        collision_model: Models,
        settings: UrlSettings,
    ) -> None:

        super(KinectAzure, self).__init__(obj_id, name, pose, collision_model, settings)

        if self._started():
            self._stop()

        self._start()  # TODO start with user-set parameters
        self.color_camera_params = rest.call(
            rest.Method.GET, f"{self.settings.url}/color/parameters", return_type=CameraParameters
        )

    @property
    def settings(self) -> UrlSettings:  # type: ignore
        return super(KinectAzure, self).settings

    def _start(self) -> None:
        rest.call(rest.Method.PUT, f"{self.settings.url}/state/start")

    def color_image(self, *, an: None | str = None) -> Image.Image:
        return rest.get_image(f"{self.settings.url}/color/image")

    def depth_image(self, averaged_frames: int = 1, *, an: None | str = None) -> Image.Image:
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

    color_image.__action__ = ActionMetadata()  # type: ignore
    # depth_image.__action__ = ActionMetadata()  # type: ignore
