import json
import os
from dataclasses import dataclass
from functools import cache
from typing import Any, Callable, Optional, TypeVar
from urllib.parse import urljoin, urlparse

from PIL import Image

from arcor2.data.camera import CameraParameters
from arcor2.data.common import ActionMetadata, BodyJointId, Direction, Pose, Position, StrEnum
from arcor2.data.object_type import Models
from arcor2.object_types.abstract import Camera, Settings
from arcor2.rest import Method, OptParams, RestException, call, get_image


class BodyJoint(StrEnum):
    PELVIS = "Pelvis"
    SPINE_CHEST = "Spine Chest"
    NECK = "Neck"
    SHOULDER_LEFT = "Shoulder Left"
    ELBOW_LEFT = "Elbow Left"
    HAND_LEFT = "Hand Left"
    SHOULDER_RIGHT = "Shoulder Right"
    ELBOW_RIGHT = "Elbow Right"
    HAND_RIGHT = "Hand Right"
    HIP_LEFT = "Hip Left"
    KNEE_LEFT = "Knee Left"
    FOOT_LEFT = "Foot Left"
    HIP_RIGHT = "Hip Right"
    KNEE_RIGHT = "Knee Right"
    FOOT_RIGHT = "Foot Right"
    HEAD = "Head"
    NOSE = "Nose"
    EYE_LEFT = "Eye Left"
    EAR_LEFT = "Ear Left"
    EYE_RIGHT = "Eye Right"
    EAR_RIGHT = "Ear Right"

    def to_id(self) -> BodyJointId:
        return {
            self.PELVIS: BodyJointId.PELVIS,
            self.SPINE_CHEST: BodyJointId.SPINE_CHEST,
            self.NECK: BodyJointId.NECK,
            self.SHOULDER_LEFT: BodyJointId.SHOULDER_LEFT,
            self.ELBOW_LEFT: BodyJointId.ELBOW_LEFT,
            self.HAND_LEFT: BodyJointId.HAND_LEFT,
            self.SHOULDER_RIGHT: BodyJointId.SHOULDER_RIGHT,
            self.ELBOW_RIGHT: BodyJointId.ELBOW_RIGHT,
            self.HAND_RIGHT: BodyJointId.HAND_RIGHT,
            self.HIP_LEFT: BodyJointId.HIP_LEFT,
            self.KNEE_LEFT: BodyJointId.KNEE_LEFT,
            self.FOOT_LEFT: BodyJointId.FOOT_LEFT,
            self.HIP_RIGHT: BodyJointId.HIP_RIGHT,
            self.KNEE_RIGHT: BodyJointId.KNEE_RIGHT,
            self.FOOT_RIGHT: BodyJointId.FOOT_RIGHT,
            self.HEAD: BodyJointId.HEAD,
            self.NOSE: BodyJointId.NOSE,
            self.EYE_LEFT: BodyJointId.EYE_LEFT,
            self.EAR_LEFT: BodyJointId.EAR_LEFT,
            self.EYE_RIGHT: BodyJointId.EYE_RIGHT,
            self.EAR_RIGHT: BodyJointId.EAR_RIGHT,
        }[self]


@dataclass
class UrlSettings(Settings):
    url: str = "http://192.168.104.100:5017"

    @classmethod
    def from_env(cls) -> "UrlSettings":
        url = os.getenv("ARCOR2_KINECT_AZURE_URL", "http://192.168.104.100:5017")
        return cls(url)

    def construct_path(self, path: str) -> str:
        @cache
        def get_base_url(url: str) -> str:
            parsed = urlparse(url)
            if parsed.netloc == "":
                parsed = urlparse("http://" + url)
            return parsed.geturl()

        return urljoin(get_base_url(self.url), path)


F = TypeVar("F", bound=Callable[..., Any])


class KinectAzure(Camera):
    _ABSTRACT = False
    mesh_filename = "kinect_azure.dae"

    def __init__(
        self,
        obj_id: str,
        name: str,
        pose: Pose,
        collision_model: Models,
        settings: Optional[UrlSettings] = None,
    ) -> None:
        if settings is None:
            settings = UrlSettings.from_env()
        super().__init__(obj_id, name, pose, collision_model, settings)
        self.start()
        self._fill_camera_parameters()

    def construct_path(self, relative_url: str) -> str:
        return self.settings.construct_path(relative_url)  # type: ignore

    def _fill_camera_parameters(self) -> None:
        self.color_camera_params = call(
            Method.GET, self.construct_path("/color/parameters"), return_type=CameraParameters
        )

    def _communicate_image(self, relative_path: str, params: OptParams = None) -> Image.Image:
        full_path = self.settings.construct_path(relative_path)  # type: ignore
        return get_image(full_path, params=params, raw_params=True)

    @property
    def _started(self) -> bool:
        ret = call(Method.GET, self.construct_path("/state/started"), return_type=bool)
        return ret

    def start(self) -> bool:
        if self._started:
            return True

        try:
            call(Method.PUT, self.construct_path("/state/full-start"), body=self.pose, return_type=str)
            return True
        except RestException:
            return False

    def stop(self) -> None:
        if not self._started:
            return

        call(Method.PUT, self.construct_path("/state/stop"))

    def cleanup(self) -> None:
        self.stop()

    def set_pose(self, pose: Pose) -> None:
        call(Method.PUT, self.construct_path("/state/pose"), body=pose)
        super().set_pose(pose)

    def color_image(self, *, an: Optional[str] = None) -> Image.Image:
        """Get color image from kinect.

        :return: Color image
        """
        return self._communicate_image("/color/image")

    def depth_image(self, averaged_frames: int = 1, *, an: Optional[str] = None) -> Image.Image:
        """Get depth image from kinect.

        :param: averaged_frames: Number of frames to get depth from (more frames, more accurate)
        :return: Depth image
        """
        assert isinstance(averaged_frames, int)
        return self._communicate_image("/depth/image", params={"num_frames": averaged_frames})

    def is_body_part_nearby(
        self, joint: BodyJoint, radius: float, position: Position, wait: bool = False, *, an: Optional[str] = None
    ) -> bool:
        """Checks if body part is in radius from pose.

        :param: joint: Body part, see: https://docs.microsoft.com/en-us/azure/kinect-dk/body-joints
        :param: radius: radius around body part in m
        :param: pose: If set, sets position in kinect otherwise use last set position
        :param: wait: Block task until the result is True
        :return: True if body part is nearby, otherwise False
        """
        joint_id = joint.to_id()
        assert 0 <= joint_id <= 31

        ret = call(
            Method.GET,
            self.construct_path("/position/is-nearby"),
            params={"joint_id": int(joint_id), "radius": radius, "wait": json.dumps(wait)},
            raw_params=True,
            return_type=bool,
            body=position,
        )
        return ret

    def get_people_count(self, *, an: Optional[str] = None) -> int:
        """Counts number of skeletons in frame.

        :return: Number of skeletons in frame
        """
        ret = call(Method.GET, self.construct_path("/body/count"), return_type=int)
        return ret

    def is_user_present(self, wait: bool = False, *, an: Optional[str] = None) -> bool:
        """Checks if any user is in frame.

        :param: wait: Block task until the result is True
        :return: True if any user is in frame, otherwise False
        """
        ret = call(
            Method.GET,
            self.construct_path("/body/present"),
            params={"wait": json.dumps(wait)},
            raw_params=True,
            return_type=bool,
        )
        return ret

    def is_body_part_moving(
        self,
        joint: BodyJoint,
        speed: float,
        direction: Position,
        deviation: float = 0.1,
        num_samples: int = 5,
        *,
        an: Optional[str] = None,
    ) -> bool:
        """Checks if a body part is moving in specified direction.

        :param: joint_id: Id of body part, see: https://docs.microsoft.com/en-us/azure/kinect-dk/body-joints
        :param: threshold: Minimum speed of moving body part in m/s
        :param: direction: Direction provided as Position
        :params: num_samples: How many samples to use to calculate speed
        :return: True if body part is moving else False
        """
        joint_id = joint.to_id()
        assert 0 <= joint_id <= 31
        direction_ = Direction.from_position(direction)
        ret = call(
            Method.GET,
            self.construct_path("/aggregation/is-moving"),
            params={"joint_id": int(joint_id), "speed": speed, "num_samples": num_samples, "deviation": deviation},
            raw_params=True,
            return_type=bool,
            body=direction_,
        )
        return ret

    def is_colliding(self, threshold: float, position: Position, *, an: Optional[str] = None) -> bool:
        """Check if any body part is colliding with specified position.

        :param: threshold: Max distance from set position in m
        :return: True if colliding else False
        """
        ret = call(
            Method.GET,
            self.construct_path("/position/is-colliding"),
            params={"threshold": threshold},
            raw_params=True,
            return_type=bool,
            body=position,
        )
        return ret

    def get_position(self, joint: BodyJoint, body_id: int = 0, an: Optional[str] = None) -> Pose:
        """Get body part position.

        :param: joint: Body part, see: https://docs.microsoft.com/en-us/azure/kinect-dk/body-joints
        :param: threshold: Minimum speed of moving body part in m/s
        :return: Pose
        """
        joint_id = joint.to_id()
        ret = call(
            Method.GET,
            self.construct_path("/position/get"),
            params={"body_id": body_id, "joint_id": int(joint_id)},
            raw_params=True,
            return_type=Pose,
        )
        return ret

    color_image.__action__ = ActionMetadata()  # type: ignore
    depth_image.__action__ = ActionMetadata()  # type: ignore
    is_body_part_nearby.__action__ = ActionMetadata(composite=True)  # type: ignore
    get_people_count.__action__ = ActionMetadata(composite=True)  # type: ignore
    is_user_present.__action__ = ActionMetadata(composite=True)  # type: ignore
    is_body_part_moving.__action__ = ActionMetadata(composite=True)  # type: ignore
    is_colliding.__action__ = ActionMetadata(composite=True)  # type: ignore
    get_position.__action__ = ActionMetadata()  # type: ignore
