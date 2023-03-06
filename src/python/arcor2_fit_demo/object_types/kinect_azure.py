from dataclasses import dataclass
from io import BytesIO

from PIL import Image

from arcor2 import rest
from arcor2.clients import scene_service
from arcor2.data.camera import CameraParameters
from arcor2.data.common import ActionMetadata, Pose
from arcor2.data.object_type import Models
from arcor2.object_types.abstract import Camera

from .fit_common_mixin import FitCommonMixin, UrlSettings  # noqa:ABS101


@dataclass
class KinectAzureSettings(UrlSettings):
    url: str = "http://fit-demo-kinect:5016"


class KinectAzure(FitCommonMixin, Camera):
    _ABSTRACT = False
    mesh_filename = "kinect_azure.dae"

    def __init__(
        self,
        obj_id: str,
        name: str,
        pose: Pose,
        collision_model: Models,
        settings: KinectAzureSettings,
    ) -> None:
        super(KinectAzure, self).__init__(obj_id, name, pose, collision_model, settings)

        if self._started():
            self._stop()

        self._start(pose)  # TODO start with user-set parameters
        self.color_camera_params = rest.call(
            rest.Method.GET, f"{self.settings.url}/color/parameters", return_type=CameraParameters
        )

    def _start(self, pose: Pose) -> None:
        rest.call(rest.Method.PUT, f"{self.settings.url}/state/start", body=pose)

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

    @property
    def pose(self) -> Pose:
        """Returns pose of the object.

        When set, pose of the collision model is updated on the Scene service.
        :return:
        """
        return rest.call(rest.Method.GET, f"{self.settings.url}/state/pose", return_type=Pose)

    @pose.setter
    def pose(self, pose: Pose) -> None:
        # TODO call those two in parallel?
        if self._enabled:  # TODO call super()?
            scene_service.upsert_collision(self.collision_model, pose)

        rest.call(rest.Method.PUT, f"{self.settings.url}/state/pose", body=pose)

    color_image.__action__ = ActionMetadata()  # type: ignore
    # depth_image.__action__ = ActionMetadata()  # type: ignore
