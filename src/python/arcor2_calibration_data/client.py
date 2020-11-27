from io import BytesIO

from arcor2_calibration_data import CALIBRATION_URL
from PIL.Image import Image

from arcor2 import rest
from arcor2.data.camera import CameraParameters
from arcor2.data.common import Pose


def estimate_camera_pose(camera: CameraParameters, image: Image) -> Pose:

    with BytesIO() as buff:

        image.save(buff, format="PNG")

        return rest.call(
            rest.Method.PUT,
            f"{CALIBRATION_URL}/calibration",
            params=camera.to_dict(),
            return_type=Pose,
            files={"image": buff.getvalue()},
        )
