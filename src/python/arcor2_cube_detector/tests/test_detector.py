import numpy as np
import open3d as o3d

from arcor2.data.camera import CameraParameters
from arcor2_cube_detector import get_data
from arcor2_cube_detector.cube_detector import Color, CubeDetector, Plane

camera_parameters = CameraParameters(
    907.80126953125,
    907.6754150390625,
    960.291259765625,
    552.93536376953125,
    [0.447, -2.5, 0.00094, -0.00053, 1.432, 0.329, -2.332, 1.363],
)
detector = CubeDetector(camera_parameters)


def test_get_image_from_bytes() -> None:
    with open(get_data("tests/color.bytes"), "rb") as file:
        color_bytes = file.read()
    with open(get_data("tests/depth.bytes"), "rb") as file:
        depth_bytes = file.read()

    color, depth = detector.get_image_from_bytes(color_bytes, depth_bytes)
    assert color, depth


def test_get_image_from_file() -> None:
    color, depth = detector.get_image_from_file(get_data("tests/color.jpg"), get_data("tests/depth.png"))
    assert color, depth


def test_filter_pointcloud() -> None:
    color = o3d.io.read_image(get_data("tests/color.jpg"))
    depth = o3d.io.read_image(get_data("tests/depth.png"))

    pointcloud_filtered = detector.filter_pointcloud(color, depth)

    assert len(pointcloud_filtered[Color.RED].points) > 0
    assert len(pointcloud_filtered[Color.GREEN].points) > 0
    assert len(pointcloud_filtered[Color.BLUE].points) > 0
    assert len(pointcloud_filtered[Color.YELLOW].points) > 0


def test_dbscan() -> None:
    points = np.array([[0, 0, 0], [1, 1, 1]])
    pcd = o3d.geometry.PointCloud()
    pcd.points = o3d.utility.Vector3dVector(points)
    assert len(detector.dbscan(pcd)) == 0

    pcd_red = o3d.io.read_point_cloud(get_data("tests/RED.pcd"))
    assert len(detector.dbscan(pcd_red)) == 4


def test_segment_plane() -> None:
    points = np.array([[0, 0, 0], [1, 1, 1]])

    pcd = o3d.geometry.PointCloud()
    pcd.points = o3d.utility.Vector3dVector(points)
    assert len(detector.segment_plane(pcd)) == 0


def test_get_angles_between_planes() -> None:
    planes = [
        Plane(None, [1.0, 0, 0, 0]),
        Plane(None, [0, 1.0, 0, 0]),
        Plane(None, [0, 0, 1.0, 0]),
        Plane(None, [1.0, 1.0, 0, 0]),
    ]

    angles = detector.get_angles_between_planes(planes)

    assert angles[0][0] == 0
    assert angles[0][1] == 90
    assert angles[0][2] == 90
    assert angles[0][3] == 45
    assert angles[1][2] == angles[2][1]


def test_is_plane_perpendicular() -> None:
    assert detector.is_plane_perpendicular(90)
    assert detector.is_plane_perpendicular(60)
    assert not detector.is_plane_perpendicular(30)
    assert not detector.is_plane_perpendicular(180)


def test_is_point_on_plane() -> None:
    point = np.array([0, 0, 0])
    assert detector.is_point_on_plane(point, [1.0, 0, 0, 0])
    assert not detector.is_point_on_plane(point, [1.0, 2.0, 3.0, 4.0])


def test_is_point_on_edge() -> None:
    point = np.array([0, 0, 0])
    assert detector.is_point_on_edge(point, [[1.0, 0, 0, 0], [0, 1.0, 0, 0]])
    assert not detector.is_point_on_edge(point, [[1.0, 0, 0, 0], [0, 1.0, 0, 1.0]])


def test_is_point_on_corner() -> None:
    point = np.array([0, 0, 0])
    assert detector.is_point_on_corner(point, [[1.0, 0, 0, 0], [0, 1.0, 0, 0], [0, 1.0, 1.0, 0]])
    assert not detector.is_point_on_corner(point, [[1.0, 0, 0, 1.0], [0, 1.0, 0, 0], [0, 1.0, 1.0, 0]])
    assert not detector.is_point_on_corner(point, [[1.0, 0, 0, 1.0], [0, 1.0, 0, 2.0], [0, 1.0, 1.0, 3.0]])


def test_find_candidates() -> None:
    angles = {0: {0: 0, 1: 90, 2: 90}, 1: {0: 90, 1: 0, 2: 90}, 2: {0: 90, 1: 90, 2: 0}}
    assert detector.find_candidates(angles) == [[0, 1, 2], [0, 1], [0, 2], [1, 2]]

    angles = {0: {0: 0, 1: 90, 2: 30}, 1: {0: 90, 1: 0, 2: 15}, 2: {0: 30, 1: 15, 2: 0}}
    assert detector.find_candidates(angles) == [[0, 1]]

    angles = {0: {0: 0, 1: 10}, 1: {0: 10, 1: 0}}
    assert detector.find_candidates(angles) == []
