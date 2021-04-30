import time

from arcor2_calibration_data import client as calib_client

from arcor2.data.common import Pose
from arcor2_fit_demo.object_types.kinect_azure import KinectAzure, UrlSettings


def main() -> None:

    kinect = KinectAzure("", "", Pose(), settings=UrlSettings("http://localhost:5016"))
    # print(kinect.color_camera_params)
    assert kinect.color_camera_params
    ci_start = time.monotonic()
    color_image = kinect.color_image()
    print(f"Time to get color_image: {time.monotonic()-ci_start}")

    calib_start = time.monotonic()
    print(calib_client.estimate_camera_pose(kinect.color_camera_params, color_image))
    print(f"Time to get calibration: {time.monotonic()-calib_start}")


if __name__ == "__main__":
    main()
