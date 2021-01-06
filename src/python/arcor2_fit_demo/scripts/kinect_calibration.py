from arcor2_calibration_data import client as calib_client

from arcor2.data.common import Pose
from arcor2_fit_demo.object_types.kinect_azure import KinectAzure


def main() -> None:

    kinect = KinectAzure("", "", Pose())
    print(kinect.color_camera_params)
    assert kinect.color_camera_params
    print(calib_client.estimate_camera_pose(kinect.color_camera_params, kinect.color_image()))


if __name__ == "__main__":
    main()
