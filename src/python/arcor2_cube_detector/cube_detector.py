import math
import os
import tempfile
import time
from dataclasses import dataclass, field
from enum import Enum
from functools import wraps
from typing import NamedTuple

import cv2
import numpy as np
import open3d as o3d
from dataclasses_jsonschema import JsonSchemaMixin

import arcor2.transformations as tr
from arcor2 import env, rest
from arcor2.data.camera import CameraParameters
from arcor2.data.common import Pose, Position
from arcor2.logging import get_logger

logger = get_logger(__name__)
if env.get_bool("ARCOR2_CUBE_DETECTOR_DEBUG"):
    logger.setLevel("DEBUG")


URL_KINECT = os.getenv("ARCOR2_KINECT_AZURE_URL", "http://0.0.0.0:5016")


@dataclass
class Cube(JsonSchemaMixin):
    color: str
    pose: Pose = field(default_factory=Pose)


class Color(Enum):
    RED = 0
    GREEN = 1
    BLUE = 2
    YELLOW = 3


class Plane(NamedTuple):
    pointcloud: o3d.geometry.PointCloud
    model: list[float]


HSV = {
    Color.BLUE: [[np.array([100, 175, 75]), np.array([135, 255, 255])]],
    Color.RED: [
        [np.array([0, 100, 50]), np.array([10, 255, 255])],
        [np.array([165, 100, 50]), np.array([180, 255, 255])],
    ],
    Color.YELLOW: [[np.array([28, 100, 50]), np.array([40, 255, 255])]],
    Color.GREEN: [[np.array([40, 100, 50]), np.array([85, 255, 255])]],
}

HALF_OF_CUBE_SIZE = 0.0125
MIN_PLANE_POINTS = 50
MAX_PLANE_POINTS = 500
COMPARE_PLANES_MIN_ANGLE = 50

step_duration: dict[list[float]] = {}


def timer(f):
    @wraps(f)
    def wrapped(*args, **kwargs):
        start = time.monotonic()
        result = f(*args, **kwargs)
        end = time.monotonic()

        global step_duration
        if f.__name__ not in step_duration.keys():
            step_duration[f.__name__] = []
        step_duration[f.__name__].append(end - start)

        return result

    return wrapped


class CubeDetector:
    def __init__(self, camera_parameters: CameraParameters, image_width: int = 1920, image_height: int = 1080) -> None:
        self.camera_parameters = o3d.camera.PinholeCameraIntrinsic(
            image_width,
            image_height,
            camera_parameters.fx,
            camera_parameters.fy,
            camera_parameters.cx,
            camera_parameters.cy,
        )

    def get_image_from_bytes(
        self, color_bytes: bytes, depth_bytes: bytes
    ) -> tuple[o3d.geometry.Image, o3d.geometry.Image]:
        """Creates color and depth image stored as bytes.

        :param color_bytes: Color image bytes
        :param depth_bytes: Depth image bytes
        :return: Color image, Depth image
        """
        with tempfile.NamedTemporaryFile(suffix=".jpg") as tmp:
            tmp.write(color_bytes)
            color = o3d.io.read_image(tmp.name)

        with tempfile.NamedTemporaryFile(suffix=".png") as tmp:
            tmp.write(depth_bytes)
            depth = o3d.io.read_image(tmp.name)
        return color, depth

    def get_image_from_file(self, color_file: str, depth_file: str) -> tuple[o3d.geometry.Image, o3d.geometry.Image]:
        """Creates color and depth image from filename.

        :param color_file: Color image filename
        :param depth_file: Depth image filename
        :return: Color image, Depth image
        """
        color = o3d.io.read_image(color_file)
        depth = o3d.io.read_image(depth_file)
        return color, depth

    def detect_cubes(
        self, color: o3d.geometry.Image, depth: o3d.geometry.Image, transform_cordinates=True
    ) -> list[Cube]:
        """Detects cubes.

        :param color: Color image
        :param depth: Depth image
        :param transform_cordinates: Transform edge coordinates to arcor2 coordinates, defaults to True
        :return: List of detected cubes
        """
        detected_cubes: list[Cube] = []

        pointcloud_filtered = self.filter_pointcloud(color, depth)

        for cube_color in Color:
            for cluster in self.dbscan(pointcloud_filtered[cube_color]):
                planes = self.segment_plane(cluster)
                angle_of_planes = self.get_angles_between_planes(planes)
                for candidate in self.find_candidates(angle_of_planes):
                    pose = self.detect_cube([planes[i] for i in candidate], transform_cordinates)
                    if pose:
                        detected_cubes.append(Cube(cube_color.name, pose))
                        break

        logger.debug(f"Detected {len(detected_cubes)} cubes")
        for key, value in step_duration.items():
            logger.debug(f"{sum(value):.5f}s - {key}")
        step_duration.clear()

        return detected_cubes

    @timer
    def filter_pointcloud(
        self, color: o3d.geometry.Image, depth: o3d.geometry.Image
    ) -> dict[Color, o3d.geometry.PointCloud]:
        """Filters input image by color and creates individual pointclouds for
        each color.

        :param color: Color image
        :param depth: Depth image
        :return: Dictionary containing pointcloud for each color
        """
        pcd_filtered: dict[Color, o3d.geometry.PointCloud] = {}

        color = np.asarray(color)
        depth = np.asarray(depth)
        hsv = cv2.cvtColor(color, cv2.COLOR_RGB2HSV)
        for cube_color in Color:
            mask = None
            for range in HSV[cube_color]:
                temp_mask = cv2.inRange(hsv, range[0], range[1])
                mask = temp_mask if mask is None else mask + temp_mask

            color_filtered = o3d.geometry.Image((cv2.bitwise_and(color, color, mask=mask)).astype(np.uint8))
            depth_filtered = o3d.geometry.Image((cv2.bitwise_and(depth, depth, mask=mask)).astype(np.uint16))

            rgbd_image_filtered = o3d.geometry.RGBDImage.create_from_color_and_depth(
                color_filtered, depth_filtered, convert_rgb_to_intensity=False
            )

            pcd_filtered[cube_color] = (
                o3d.geometry.PointCloud()
                .create_from_rgbd_image(rgbd_image_filtered, self.camera_parameters)
                .voxel_down_sample(voxel_size=0.0015)
            )
        return pcd_filtered

    @timer
    def dbscan(self, pointcloud: o3d.geometry.PointCloud) -> list[o3d.geometry.PointCloud]:
        """Performs dbscan clustering and saves each cluster as individual
        pointcloud.

        :param pointcloud: Filtered pointcloud
        :return: List of pointcloud segments
        """
        if len(pointcloud.points) < 2 * MIN_PLANE_POINTS:
            return []

        labels = np.array(pointcloud.cluster_dbscan(eps=0.015, min_points=MIN_PLANE_POINTS, print_progress=False))

        cluster_count = labels.max() + 1
        pointcloud_clusters = [None] * cluster_count
        for i in range(cluster_count):
            index = np.where(labels == i)[0]
            pointcloud_clusters[i] = pointcloud.select_by_index(index)
        return pointcloud_clusters

    @timer
    def segment_plane(self, cluster: o3d.geometry.PointCloud) -> list[Plane]:
        """Segments cluster pointcloud into planes.

        :param cluster: Cluster pointcloud
        :return: List of planes containing pointcloud and model of the plane
        """
        _, ind = cluster.remove_statistical_outlier(nb_neighbors=20, std_ratio=2.0)
        outlier = cluster.select_by_index(ind)

        planes: list[Plane] = []
        while outlier.has_points() and len(outlier.points) > MIN_PLANE_POINTS:
            plane_model, inliers = outlier.segment_plane(distance_threshold=0.002, ransac_n=3, num_iterations=100)
            inlier = outlier.select_by_index(inliers)
            outlier = outlier.select_by_index(inliers, invert=True)
            if len(inlier.points) > MIN_PLANE_POINTS and len(inlier.points) < MAX_PLANE_POINTS:
                planes.append(Plane(inlier, plane_model))
        return planes

    @timer
    def get_angles_between_planes(self, planes: list[Plane]) -> dict[int, dict[int, int]]:
        """Creates table with angles between each plane.

        :param planes: List of planes
        :return: Table with angles between each plane
        """
        plane_angles: dict[int, dict[int, int]] = {}

        for i, (_, [a1, b1, c1, _]) in enumerate(planes):
            plane_angles[i] = {}
            for j, (_, [a2, b2, c2, _]) in enumerate(planes):
                if i == j:
                    angle = 0
                else:
                    # Inspired by https://www.geeksforgeeks.org/angle-between-two-planes-in-3d/
                    d = a1 * a2 + b1 * b2 + c1 * c2
                    e1 = math.sqrt(a1 * a1 + b1 * b1 + c1 * c1)
                    e2 = math.sqrt(a2 * a2 + b2 * b2 + c2 * c2)
                    d = d / (e1 * e2)
                    angle = round(math.degrees(math.acos(d)))
                plane_angles[i][j] = angle
        return plane_angles

    def is_plane_perpendicular(self, angle: int) -> bool:
        """Checks if angle of the plane is perpendicular.

        :param angle: Angle of the plane
        :return: True if angle is perpendicular, False otherwise
        """
        return angle >= COMPARE_PLANES_MIN_ANGLE and angle <= 180 - COMPARE_PLANES_MIN_ANGLE

    def is_point_on_plane(self, point: np.ndarray, plane_model: list[float]) -> bool:
        """Checks if point is on the plane.

        :param point: Point with 3D coordinates
        :param plane_model: Plane model
        :return: True if point is on the plane, False otherwise
        """
        return (
            abs(point[0] * plane_model[0] + point[1] * plane_model[1] + point[2] * plane_model[2] + plane_model[3])
            < 0.004
        )

    def is_point_on_edge(self, point: np.ndarray, plane_models: list[list[float]]) -> bool:
        """Checks, if point is on the intersection of two planes.

        :param point: Point with 3D coordinates
        :param plane_models: Plane models of two planes forming an edge
        :return:  True if point is on the intersection, False otherwise
        """
        return self.is_point_on_plane(point, plane_models[0]) and self.is_point_on_plane(point, plane_models[1])

    def is_point_on_corner(self, point: np.ndarray, plane_models: list[list[float]]) -> bool:
        """Checks, if point is the corner of cube (if point is on every edge)

        :param point: Point with 3D coordinates
        :param plane_models: Plane models of three planes forming a corner
        :return: True if point is the corner of cube
        """
        return (
            self.is_point_on_edge(point, [plane_models[0], plane_models[1]])
            and self.is_point_on_edge(point, [plane_models[0], plane_models[2]])
            and self.is_point_on_edge(point, [plane_models[1], plane_models[2]])
        )

    @timer
    def find_candidates(self, angle_between_planes: dict[int, dict[int, int]]) -> list[list[int]]:
        """Finds cube candidates from cluster pointcloud.

        :param angle_between_planes: Table with angles for each plane
        :return: List of plane IDs, that can potentially form a cube
        """

        candidates: list[list[int]] = []

        # Compare plane angles with each other
        for reference_plane_1_ID in angle_between_planes.keys():
            for reference_plane_2_id in angle_between_planes[reference_plane_1_ID].keys():
                if reference_plane_1_ID == reference_plane_2_id:
                    continue
                if self.is_plane_perpendicular(angle_between_planes[reference_plane_1_ID][reference_plane_2_id]):
                    # Add candidate with 2 sides if it isnt already added
                    if sorted([reference_plane_1_ID, reference_plane_2_id]) not in candidates:
                        candidates.append(sorted([reference_plane_1_ID, reference_plane_2_id]))
                    for reference_plane_3_ID in angle_between_planes[reference_plane_1_ID].keys():
                        # Plane has 2 "perpendicular" planes
                        candidate = sorted([reference_plane_1_ID, reference_plane_2_id, reference_plane_3_ID])
                        if (
                            reference_plane_3_ID in [reference_plane_1_ID, reference_plane_2_id]
                            or candidate in candidates
                        ):
                            continue

                        if self.is_plane_perpendicular(
                            angle_between_planes[reference_plane_1_ID][reference_plane_3_ID]
                        ) and self.is_plane_perpendicular(
                            angle_between_planes[reference_plane_2_id][reference_plane_3_ID]
                        ):
                            # All 3 planes are "perpendicular" to each other
                            candidates.insert(0, candidate)
        return candidates

    @timer
    def detect_cube(self, candidates: list[Plane], transform_cordinates: bool) -> Pose | None:
        """Detects cube in cluster by comparing perpendicular planes.

        :param candidates: Planes that potentialy form a cube
        :param transform_cordinates: Transform coordinates to arcor2 coordinate system
        :return: Returns pose if cube is detected, None otherwise
        """

        cube_pointcloud = o3d.geometry.PointCloud()
        for plane_pointcloud, _ in candidates:
            cube_pointcloud += plane_pointcloud

        # Create bounding box and check distance between max and min bound
        # If the distane is larger than 0.1, it probably isn't a cube
        # This removes most of the false positive detections
        bounding_box = o3d.geometry.OrientedBoundingBox.create_from_points(cube_pointcloud.points)
        if np.linalg.norm(bounding_box.get_max_bound() - bounding_box.get_min_bound()) > 0.125:
            return None

        points = np.asarray(cube_pointcloud.points)

        number_of_sides = len(candidates)

        # Get points of edges
        edge_points: list = number_of_sides * [None]
        for i in range(number_of_sides):
            edge_points[i] = [
                point
                for point in points
                if self.is_point_on_edge(point, [candidates[i].model, candidates[(i + 1) % number_of_sides].model])
            ]
        edge = o3d.geometry.PointCloud()
        edge.points = o3d.utility.Vector3dVector(sum(edge_points, []))

        if number_of_sides == 3:
            # Cube has 3 sides, get corner position
            corner = o3d.geometry.PointCloud()
            corner.points = o3d.utility.Vector3dVector(
                [point for point in points if self.is_point_on_corner(point, [plane.model for plane in candidates])]
            )
            center = np.asarray(corner.get_center())
        else:
            # Cube has 2 sides and only 1 edge, get position of center of the edge
            center = np.asarray(edge.get_center())

        vector: list = number_of_sides * [None]
        vector_distance: list = number_of_sides * [0]
        for i in range(number_of_sides):
            if number_of_sides == 3:
                edge_center = o3d.geometry.PointCloud()
                edge_center.points = o3d.utility.Vector3dVector(edge_points[i])
                edge_center = edge_center.get_center()
            else:
                edge_center = candidates[i].pointcloud.get_center()

            # Calculate direction vector from corner to edge center
            vector[i] = 3 * [None]
            for j in range(3):
                vector[i][j] = edge_center[j] - center[j]

            # Normalize vector
            norm = np.linalg.norm(vector[i])
            if norm != 0:
                vector[i] /= norm

            # Calculate distance from corner to edge center
            vector_distance[i] = np.linalg.norm(center - np.asarray(edge_center))

        # If the average distance from corner to edge center is larger than threshold, it probably isn't a cube
        if abs(HALF_OF_CUBE_SIZE - np.average(vector_distance)) > 0.2:
            return None

        # Calculate center coordinates by adding half the cube size to each side from the corner
        for i in range(3):
            for j in range(number_of_sides):
                center[i] += vector[j][i] * HALF_OF_CUBE_SIZE

        pose = Pose(Position(*center))

        # Transform coordinates to arcor2 coordinate system
        if transform_cordinates:
            kinect_pose = rest.call(rest.Method.GET, f"{URL_KINECT}/state/pose", return_type=Pose)
            pose = tr.make_pose_abs(kinect_pose, pose)

        return pose
