from dataclasses import dataclass
from io import BytesIO
from typing import List

from arcor2_calibration_data import CALIBRATION_URL, EstimatedPose, MarkerCorners
from dataclasses_jsonschema import JsonSchemaMixin
from PIL.Image import Image

from arcor2 import rest
from arcor2.data.camera import CameraParameters
from arcor2.data.common import Joint, Pose


def markers_corners(camera: CameraParameters, image: Image) -> List[MarkerCorners]:

    with BytesIO() as buff:

        image.save(buff, format="PNG")

        return rest.call(
            rest.Method.PUT,
            f"{CALIBRATION_URL}/markers/corners",
            params=camera.to_dict(),
            list_return_type=MarkerCorners,
            files={"image": buff.getvalue()},
        )


def estimate_camera_pose(camera: CameraParameters, image: Image, inverse: bool = False) -> EstimatedPose:
    """Returns camera pose with respect to the origin.

    :param camera: Camera parameters.
    :param image: Image.
    :param inverse: When set, the method returns pose of the origin wrt. the camera.
    :return:
    """

    with BytesIO() as buff:

        image.save(buff, format="PNG")

        params = camera.to_dict()
        params["inverse"] = inverse

        return rest.call(
            rest.Method.PUT,
            f"{CALIBRATION_URL}/calibrate/camera",
            params=params,
            return_type=EstimatedPose,
            files={"image": buff.getvalue()},
        )


@dataclass
class CalibrateRobotArgs(JsonSchemaMixin):

    robot_joints: List[Joint]
    robot_pose: Pose
    camera_pose: Pose
    camera_parameters: CameraParameters
    urdf_uri: str


def calibrate_robot(args: CalibrateRobotArgs, depth_image: Image) -> Pose:

    with BytesIO() as buff:
        depth_image.save(buff, format="PNG")

        return rest.call(
            rest.Method.PUT,
            f"{CALIBRATION_URL}/calibrate/robot",
            return_type=Pose,
            files={"image": buff.getvalue(), "args": args.to_json()},
            timeout=rest.Timeout(3.05, 240),
        )
