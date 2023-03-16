import csv
import os

import numpy as np

from arcor2.data.camera import CameraParameters
from arcor2.data.common import Pose, Position
from arcor2_cube_detector import get_data
from arcor2_cube_detector.cube_detector import Cube, CubeDetector


def test_dataset() -> None:
    camera_parameters = CameraParameters(
        907.80126953125,
        907.6754150390625,
        960.291259765625,
        552.93536376953125,
        [0.447, -2.5, 0.00094, -0.00053, 1.432, 0.329, -2.332, 1.363],
    )
    detector = CubeDetector(camera_parameters)
    total_matches = 0
    total_expected = 0

    path = get_data("dataset")
    assert os.path.exists(path)

    for folder in os.listdir(path):
        if not (
            os.path.exists(f"{path}/{folder}/color.jpg")
            and os.path.exists(f"{path}/{folder}/depth.png")
            and os.path.exists(f"{path}/{folder}/annotation.csv")
        ):
            continue
        color, depth = detector.get_image_from_file(
            get_data(f"dataset/{folder}/color.jpg"), get_data(f"dataset/{folder}/depth.png")
        )
        assert color
        assert depth
        detected_cubes = detector.detect_cubes(color, depth, transform_cordinates=False)
        expected_cubes: list[Cube] = []

        matches = 0

        with open(get_data(f"dataset/{folder}/annotation.csv")) as annotation:
            assert annotation
            reader = csv.reader(annotation)
            _ = next(reader)
            for row in reader:
                expected_cubes.append(Cube(row[0], Pose(Position(float(row[1]), float(row[2]), float(row[3])))))

        for cube in detected_cubes:
            for ex in expected_cubes:
                if cube.color == ex.color:
                    distance = np.linalg.norm(
                        np.array([cube.pose.position[0], cube.pose.position[1], cube.pose.position[2]])
                        - np.array([ex.pose.position[0], ex.pose.position[1], ex.pose.position[2]])
                    )
                    if distance <= 0.025:
                        matches += 1
                        break

        total_matches += matches
        total_expected += len(expected_cubes)

    pass_percentage = int((total_matches / total_expected) * 100)
    assert pass_percentage >= 70
