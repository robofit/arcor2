import os.path

from PIL import Image

from arcor2.data.common import Pose
from arcor2_calibration.calibration import estimate_camera_pose


def test_estimate_camera_pose() -> None:
    with Image.open(os.path.join(os.path.abspath(os.path.dirname(__file__)), "markers.png")) as im:
        markers = estimate_camera_pose(
            [[1, 0.00000, 1], [0.00000, 1, 1], [0.00000, 0.00000, 1]], [1.0, 1.0, 1.0, 1.0], im, 0.1
        )
        assert len(markers) == 2
        assert set(markers.keys()) == {0, 39}

        for pose in markers.values():
            assert isinstance(pose, Pose)
