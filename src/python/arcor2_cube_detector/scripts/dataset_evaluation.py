#!/usr/bin/env python3

import argparse
import csv
import logging
import os
import time
from typing import Optional

import numpy as np

from arcor2.data.camera import CameraParameters
from arcor2.data.common import Pose, Position
from arcor2.logging import get_logger
from arcor2_cube_detector import get_data
from arcor2_cube_detector.cube_detector import Cube, CubeDetector

logger = get_logger(__name__)


def evaluate(number_of_iterations: int, save_path: Optional[str] = None) -> None:
    """Evaluates dataset a prints out summary.

    :param number_of_iterations: Dataset will be evaluated multiple times and the results will be averaged
    :param save_path: Save evaluation details to CSV file in given path, defaults to None (= results won't be saved)
    """
    cameraParameters = CameraParameters(
        907.80126953125,
        907.6754150390625,
        960.291259765625,
        552.93536376953125,
        [0.447, -2.5, 0.00094, -0.00053, 1.432, 0.329, -2.332, 1.363],
    )
    detector = CubeDetector(cameraParameters)

    correct_detections: list[list[int]] = [[] for _ in range(number_of_iterations)]
    expected_detections: list[list[int]] = [[] for _ in range(number_of_iterations)]
    false_positives: list[list[int]] = [[] for _ in range(number_of_iterations)]
    detection_time: list[list[float]] = [[] for _ in range(number_of_iterations)]
    iteration_time: list[float] = [] * number_of_iterations

    for iteration in range(number_of_iterations):
        iteration_start = time.monotonic()

        path = get_data("dataset")
        assert os.path.exists(path)

        # Get only numbered folders and sort them
        folders = [folder for folder in os.listdir(path) if folder.isdigit()]
        folders.sort(key=int)

        for folder in folders:
            if not (
                os.path.exists(f"{path}/{folder}/color.jpg")
                and os.path.exists(f"{path}/{folder}/depth.png")
                and os.path.exists(f"{path}/{folder}/annotation.csv")
            ):
                continue

            detection_start = time.monotonic()
            # Load data and detect cubes
            color, depth = detector.get_image_from_file(
                get_data(f"dataset/{folder}/color.jpg"), get_data(f"dataset/{folder}/depth.png")
            )
            detected_cubes = detector.detect_cubes(color, depth, transform_cordinates=False)
            detection_end = time.monotonic()

            # Load anotated cubes
            expected_cubes: list[Cube] = []
            with open(get_data(f"dataset/{folder}/annotation.csv")) as annotation:
                reader = csv.reader(annotation)
                _ = next(reader)
                for row in reader:
                    expected_cubes.append(Cube(row[0], Pose(Position(float(row[1]), float(row[2]), float(row[3])))))

            logger.debug("")
            logger.debug(f"Folder: {folder}")
            logger.debug(f"Detected cubes: {len(detected_cubes)}")

            correctly_detected_cubes: list[int] = []

            for cube in detected_cubes:
                position = Position(*(round(pos, 5) for pos in cube.pose.position))
                for i, ex in enumerate(expected_cubes):
                    if cube.color == ex.color:
                        distance = np.linalg.norm(
                            np.array([cube.pose.position[0], cube.pose.position[1], cube.pose.position[2]])
                            - np.array([ex.pose.position[0], ex.pose.position[1], ex.pose.position[2]])
                        )
                        if distance <= 0.025:
                            correctly_detected_cubes.append(i)
                            logger.debug(f"\t✅ MATCH | {cube.color}  \t| {position}")
                            break
                else:
                    logger.debug(f"\t❌ F. P. | {cube.color}  \t| {position}")

            logger.debug(f"Expected cubes: {len(expected_cubes)}")
            for i, cube in enumerate(expected_cubes):
                logger.debug(
                    f"\t{'✅' if i in correctly_detected_cubes else '❌'} \t | {cube.color}  \t| {cube.pose.position}"
                )

            logger.debug(
                "Detected {}/{} cubes, {} false positives".format(
                    len(correctly_detected_cubes),
                    len(expected_cubes),
                    len(detected_cubes) - len(correctly_detected_cubes),
                )
            )

            correct_detections[iteration].append(len(correctly_detected_cubes))
            expected_detections[iteration].append(len(expected_cubes))
            false_positives[iteration].append(len(detected_cubes) - len(correctly_detected_cubes))
            detection_time[iteration].append(detection_end - detection_start)

            logger.debug(f"Detection time: {(detection_end - detection_start):.3f}s")

        iteration_time.append(time.monotonic() - iteration_start)

    # Print results
    logger.info("===========================================")
    logger.info("ITERATION\t|Detected/Expected|F.P.| Time ")
    logger.info("===========================================")
    for iteration in range(number_of_iterations):
        total_correct_detections = sum(correct_detections[iteration])
        total_expected_detections = sum(expected_detections[iteration])
        logger.info(
            "{}\t\t| {} / {} ({}%) | {} | {:.3f}s".format(
                iteration + 1,
                total_correct_detections,
                total_expected_detections,
                int((total_correct_detections / total_expected_detections) * 100),
                sum(false_positives[iteration]),
                iteration_time[iteration],
            )
        )
    logger.info("===========================================")
    avg_correct_detections = int(sum([sum(total) for total in correct_detections]) / number_of_iterations)
    avg_expected_detections = int(sum([sum(total) for total in expected_detections]) / number_of_iterations)
    logger.info(
        "AVG\t| {} / {} ({}%) | {} | {:.3f}s".format(
            avg_correct_detections,
            avg_expected_detections,
            int((avg_correct_detections / avg_expected_detections) * 100),
            int(sum([sum(total) for total in false_positives]) / number_of_iterations),
            sum(iteration_time) / number_of_iterations,
        )
    )
    logger.info("===========================================")

    # Save detailed results to CSV file
    if save_path:
        with open(os.path.join(save_path, f"evaluation_{time.strftime('%Y%m%d_%H%M%S')}.csv"), "w") as file:
            writer = csv.writer(file)
            writer.writerow(["iteration", "folder", "detected", "expected", "false_positives", "time"])
            for iteration in range(number_of_iterations):
                for folder_number in range(len(expected_detections[0])):
                    writer.writerow(
                        [
                            iteration + 1,
                            folder_number,
                            correct_detections[iteration][folder_number],
                            expected_detections[iteration][folder_number],
                            false_positives[iteration][folder_number],
                            detection_time[iteration][folder_number],
                        ]
                    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-d",
        "--debug",
        help="Set logging level to debug.",
        action="store_const",
        const=logging.DEBUG,
        default=logging.INFO,
    )
    parser.add_argument("-i", "--iterations", type=int, default=5)
    parser.add_argument("-s", "--save", type=str, default=None)

    args = parser.parse_args()
    logger.setLevel(args.debug)

    evaluate(args.iterations, args.save)


if __name__ == "__main__":
    main()
