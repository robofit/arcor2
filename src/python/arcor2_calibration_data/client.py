import base64
import io
import os

from arcor2_calibration_data import CameraParameters

from arcor2 import rest
from arcor2.data.common import Pose

ARCOR2_CALIBRATION_URL = os.getenv("ARCOR2_CALIBRATION_URL", "http://localhost:5014")
ARCOR2_CALIBRATION_MARKER_SIZE = float(os.getenv("ARCOR2_CALIBRATION_MARKER_SIZE", 0.1))
ARCOR2_CALIBRATION_MARKER_ID = float(os.getenv("ARCOR2_CALIBRATION_MARKER_ID", 10))


def get_marker_pose(camera: CameraParameters, base64_encoded_image: str) -> Pose:

    params_dict = camera.to_dict()

    params_dict["marker_size"] = ARCOR2_CALIBRATION_MARKER_SIZE
    params_dict["marker_id"] = ARCOR2_CALIBRATION_MARKER_ID

    with io.BytesIO(base64.b64decode(base64_encoded_image.encode())) as image:
        return rest.put(f"{ARCOR2_CALIBRATION_URL}/calibration", None, params_dict, Pose, {"image": image.getvalue()})
