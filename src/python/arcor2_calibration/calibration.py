from typing import Dict, List

import cv2  # type: ignore
import numpy as np  # type: ignore
import quaternion  # type: ignore
from cv2 import aruco

from arcor2.data.common import Orientation, Pose, Position


def get_poses(
    camera_matrix: List[List[float]], dist_matrix: List[float], img_path, marker_size: float = 0.1
) -> Dict[int, Pose]:

    camera_matrix = np.array(camera_matrix)
    dist_matrix = np.array(dist_matrix)

    img = cv2.imread(img_path)

    ret: Dict[int, Pose] = {}

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    aruco_dict = aruco.Dictionary_get(aruco.DICT_7X7_1000)
    parameters = aruco.DetectorParameters_create()

    corners, ids, rejectedImgPoints = aruco.detectMarkers(gray, aruco_dict, parameters=parameters)

    if np.all(ids is None):
        return ret

    rvec, tvec, obj_points = aruco.estimatePoseSingleMarkers(corners, marker_size, camera_matrix, dist_matrix)

    rvec = rvec.reshape(len(ids), 3)
    tvec = tvec.reshape(len(ids), 3)

    for idx, mid in enumerate(ids):

        o = Orientation()
        o.set_from_quaternion(quaternion.from_rotation_vector(rvec[idx]))
        ret[mid[0]] = Pose(Position(tvec[idx][0], tvec[idx][1], tvec[idx][2]), o)

    return ret
