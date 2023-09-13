from dataclasses import dataclass
from enum import Enum
from typing import Optional

import numpy as np
from dataclasses_jsonschema import JsonSchemaMixin

from arcor2 import env
from arcor2.data.common import Pose, Position
from arcor2.logging import get_logger
from arcor2_cube_detector.cube_detector import Cube

logger = get_logger(__name__)
if env.get_bool("ARCOR2_CUBE_TRACKER_DEBUG"):
    logger.setLevel("DEBUG")


@dataclass
class StoredCube(JsonSchemaMixin):
    cube: Cube
    up_to_date: int


class DistanceType(Enum):
    NEAREST = 0
    FARTHEST = 1


class CubeTracker:
    def __init__(self, average_position: bool = True) -> None:
        self.stored_cubes: list[StoredCube] = []
        self.average_position = average_position

    def cubes_distance(self, pos1: Position, pos2: Position) -> np.float64:
        """Returns distance between two cubes.

        :param pos1: Position 1
        :param pos2: Position 2
        :return: Distance between two positions
        """
        p1 = np.array([pos1.x, pos1.y, pos1.z])
        p2 = np.array([pos2.x, pos2.y, pos2.z])
        distance = np.linalg.norm(p1 - p2)
        return distance

    def index_of_nearest_cube(self, cube: Cube, searched_cubes: list[Cube]) -> int | None:
        """Returns index of nearest cube from list.

        :param cube: Cube to which we are looking for the nearest cube
        :param searched_cubes: List of cubes
        :return: Index of nearest cube
        """
        distances_between_cubes: list[tuple[int, np.float64]] = []
        for i, searched_cube in enumerate(searched_cubes):
            if cube.color == searched_cube.color:
                distances_between_cubes.append(
                    (i, self.cubes_distance(cube.pose.position, searched_cube.pose.position))
                )

        if len(distances_between_cubes) == 0:
            return None

        # Sort by distance
        distances_between_cubes.sort(key=lambda x: x[1])

        # Return index of nearest cube
        return distances_between_cubes[0][0]

    def store_cubes(self, detected_cubes: list[Cube]):
        """Stores cubes,

        :param detected_cubes: Cubes to store
        """

        logger.debug("STORE_CUBES INPUT:")
        for cube in detected_cubes:
            logger.debug(f"\t{cube.pose.position}")

        # Increment UpToDate index
        # Remove cubes that haven't been detected in 5 iterations
        for stored_cube in self.stored_cubes:
            stored_cube.up_to_date += 1
            if stored_cube.up_to_date > 5:
                self.stored_cubes.remove(stored_cube)
                logger.debug(f"REMOVING {stored_cube.cube.pose.position}")

        # Copy of original list, because original list will be altered during the cycle
        stored_cubes_copy = self.stored_cubes.copy()
        # Flag if cubes were updated
        updated_cubes = [False] * len(self.stored_cubes)

        while not all(updated_cubes) and detected_cubes:
            for i, stored_cube in enumerate(stored_cubes_copy):
                if updated_cubes[i]:
                    continue
                nearest_cube = self.index_of_nearest_cube(stored_cube.cube, detected_cubes)
                if nearest_cube is None:
                    # No other detected cubes with the same color
                    # Stored cube stays the same
                    updated_cubes[i] = True
                    continue
                if i == self.index_of_nearest_cube(
                    detected_cubes[nearest_cube], [cube.cube for cube in stored_cubes_copy]
                ):
                    logger.debug(
                        f"UPDATING {stored_cube.cube.pose.position} -> {detected_cubes[nearest_cube].pose.position}"
                    )
                    # Both cubes are nearest to each other
                    # Update stored cube with detected cube
                    if self.average_position:
                        # Average position
                        self.stored_cubes[i].cube.pose.position = (
                            stored_cube.cube.pose.position + detected_cubes[nearest_cube].pose.position
                        ) * 0.5
                        self.stored_cubes[i].cube.pose.orientation = detected_cubes[nearest_cube].pose.orientation
                    else:
                        self.stored_cubes[i].cube = detected_cubes[nearest_cube]
                    self.stored_cubes[i].up_to_date = 0
                    updated_cubes[i] = True

                    # Remove detected cube from list because it cant no longer update other cubes
                    del detected_cubes[nearest_cube]

        # Add detected cubes, that didn't update any stored cube
        for cube in detected_cubes:
            self.stored_cubes.append(StoredCube(cube, 0))
            logger.debug(f"ADDING {cube.pose.position}")

    def get_stored_cubes(self, color: Optional[str] = None) -> list[Pose]:
        """Returns stored cubes.

        :param color: Get only cubes of selected color, defaults to None
        :return: Poses of cubes
        """
        return [
            stored_cube.cube.pose
            for stored_cube in self.stored_cubes
            if color is None or stored_cube.cube.color == color
        ]

    def get_cube_by_distance(
        self,
        distance_type: DistanceType,
        position: Position,
        offset: Position,
        max_distance: float = 1,
        color: Optional[str] = None,
    ) -> Pose | None:
        """Returns the nearest or farthest cube from the point of interest.

        :param distance_type: Select nearest or farthest cube
        :param position: Point of interest
        :param offset: Offset that is added to center of cube
        :param max_distance: Maximum distance to consider, defaults to 1
        :param color: Color of cube, defaults to None
        :return: Pose of the nearest cube
        """
        # Calculate distance from point of intereset to each cube
        cubes = [(cube.cube, self.cubes_distance(cube.cube.pose.position, position)) for cube in self.stored_cubes]
        # Filter cubes by selected color and max distance
        filtered_cubes = list(
            filter(
                lambda cube: (color is None or cube[0].color == color) and (cube[1] < max_distance),
                cubes,
            )
        )
        if len(filtered_cubes) == 0:
            return None

        # Order by ascending distance
        filtered_cubes.sort(key=lambda cube: cube[1])

        # Reverse order for the farthest cube
        if distance_type == DistanceType.FARTHEST:
            filtered_cubes.reverse()

        # First cube in the list is nearest to/farthest from the point of interest
        cube = filtered_cubes[0][0].pose
        cube_with_offset = Pose(cube.position + offset, cube.orientation)

        logger.debug(f"RETURNING {distance_type.name} {cube_with_offset.position}")

        return cube_with_offset
