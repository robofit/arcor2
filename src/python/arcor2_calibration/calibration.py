import math

import cv2
import numpy as np
import quaternion
from cv2 import aruco
from PIL import Image

from arcor2.data.common import Orientation, Pose, Position
from arcor2.exceptions import Arcor2Exception

BLUR_THRESHOLD: float = 150.0

aruco_dict = aruco.getPredefinedDictionary(aruco.DICT_7X7_1000)
detector_params = aruco.DetectorParameters()
detector = aruco.ArucoDetector(aruco_dict, detector_params)


def detect_corners(
    camera_matrix: list[list[float]], dist_matrix: list[float], image: Image.Image, refine: bool = False
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:

    camera_matrix_arr = np.array(camera_matrix)
    dist_matrix_arr = np.array(dist_matrix)

    gray = cv2.cvtColor(np.array(image), cv2.COLOR_RGBA2GRAY)

    # scaling to a defined resolution is necessary in order to get similar results for different resolutions
    # resolution is chosen to be the same as resolution used by arcore
    # another approach could be to normalize computed variance by number of pixels
    variance_of_laplacian = cv2.Laplacian(
        cv2.resize(gray, (640, 480), interpolation=cv2.INTER_NEAREST), cv2.CV_64F
    ).var()

    if variance_of_laplacian < BLUR_THRESHOLD:
        raise Arcor2Exception(f"Blur score {variance_of_laplacian:.2f} is below the threshold.")

    # it takes 3x longer with aruco.CORNER_REFINE_APRILTAG
    detector_params.cornerRefinementMethod = aruco.CORNER_REFINE_APRILTAG if refine else aruco.CORNER_REFINE_NONE

    corners, ids, _ = detector.detectMarkers(gray)

    return camera_matrix_arr, dist_matrix_arr, gray, corners, ids


def estimate_camera_pose(
    camera_matrix: list[list[float]], dist_matrix: list[float], image: Image.Image, marker_size: float
) -> dict[int, Pose]:

    camera_matrix_arr, dist_matrix_arr, gray, corners, ids = detect_corners(
        camera_matrix, dist_matrix, image, refine=True
    )

    ret: dict[int, Pose] = {}

    if np.all(ids is None):
        return ret

    # TODO do not perform estimation for un-configured markers
    rvec, tvec, _ = aruco.estimatePoseSingleMarkers(corners, marker_size, camera_matrix_arr, dist_matrix_arr)

    rvec = rvec.reshape(len(ids), 3)
    tvec = tvec.reshape(len(ids), 3)

    if __debug__:
        backtorgb = cv2.cvtColor(gray, cv2.COLOR_GRAY2RGB)
        aruco.drawDetectedMarkers(backtorgb, corners)  # Draw A square around the markers

        for idx in range(len(ids)):
            cv2.drawFrameAxes(backtorgb, camera_matrix_arr, dist_matrix_arr, rvec[idx], tvec[idx], 0.15)

        cv2.imwrite("marker.jpg", backtorgb)

    for idx, mid in enumerate(ids):

        # convert pose of the marker wrt camera to pose of camera wrt marker
        # based on https://stackoverflow.com/a/51515560/3142796
        marker_rot_matrix, _ = cv2.Rodrigues(rvec[idx])

        assert np.allclose(np.linalg.inv(marker_rot_matrix), marker_rot_matrix.transpose())
        assert math.isclose(np.linalg.det(marker_rot_matrix), 1)

        camera_rot_matrix = marker_rot_matrix.transpose()

        camera_trans_vector = np.matmul(-camera_rot_matrix, tvec[idx].reshape(3, 1)).flatten()

        o = Orientation.from_quaternion(quaternion.from_rotation_matrix(camera_rot_matrix))
        ret[mid[0]] = Pose(Position(camera_trans_vector[0], camera_trans_vector[1], camera_trans_vector[2]), o)

    return ret
