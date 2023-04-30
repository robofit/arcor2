import numpy as np
from pyk4a import PyK4ACapture

from arcor2_kinect_azure_data.joint import BodyJoint


def parse_skeleton(capture: PyK4ACapture, body_id: int = 0) -> np.ndarray | None:
    skeleton = capture.body_skeleton
    if skeleton is None or skeleton.shape[0] == 0:
        return None
    try:
        return skeleton[body_id, :, :]
    except KeyError:
        return None


def get_body_joint(capture: PyK4ACapture, index: int, body_id: int = 0) -> BodyJoint | None:
    body_skeleton = parse_skeleton(capture, body_id)
    if body_skeleton is None:
        return None
    return BodyJoint.from_joint(body_skeleton[index])
