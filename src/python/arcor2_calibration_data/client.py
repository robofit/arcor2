from dataclasses import dataclass
from io import BytesIO
from typing import List

from arcor2_calibration_data import CALIBRATION_URL
from dataclasses_jsonschema import JsonSchemaMixin
from PIL.Image import Image

from arcor2 import rest
from arcor2.data.camera import CameraParameters
from arcor2.data.common import Joint, Pose


def estimate_camera_pose(camera: CameraParameters, image: Image) -> Pose:

    with BytesIO() as buff:

        image.save(buff, format="PNG")

        return rest.call(
            rest.Method.PUT,
            f"{CALIBRATION_URL}/calibrate/camera",
            params=camera.to_dict(),
            return_type=Pose,
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
