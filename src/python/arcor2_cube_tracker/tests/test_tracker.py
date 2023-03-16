from arcor2.data.common import Pose, Position
from arcor2_cube_detector.cube_detector import Color, Cube
from arcor2_cube_tracker.cube_tracker import CubeTracker, DistanceType, StoredCube


def test_cubes_distance() -> None:
    tracker = CubeTracker()

    assert tracker.cubes_distance(Position(0, 0, 0), Position(1, 0, 0)) == 1


def test_index_of_nearest_cube() -> None:
    tracker = CubeTracker()

    cube1 = Cube(Color.RED.name, Pose(Position(0, 0, 0)))
    cube2 = Cube(Color.YELLOW.name, Pose(Position(1, 2, 3)))

    cubes = [
        Cube(Color.RED.name, Pose(Position(5, 0, 0))),
        Cube(Color.GREEN.name, Pose(Position(1, 0, 0))),
        Cube(Color.BLUE.name, Pose(Position(0, -2, 0))),
        Cube(Color.RED.name, Pose(Position(1, 1, 1))),
        Cube(Color.RED.name, Pose(Position(0, 3, 3))),
        Cube(Color.BLUE.name, Pose(Position(-1, -1, 1))),
    ]

    assert tracker.index_of_nearest_cube(cube1, cubes) == 3
    assert tracker.index_of_nearest_cube(cube2, cubes) is None


def test_store_cubes_remove_outdated() -> None:
    tracker = CubeTracker()

    assert len(tracker.stored_cubes) == 0

    pos1 = Pose(Position(5, 0, 0))
    pos2 = Pose(Position(1, 0, 0))
    tracker.stored_cubes = [
        StoredCube(Cube(Color.RED.name, pos1), 4),
        StoredCube(Cube(Color.GREEN.name, pos2), 5),
    ]

    assert len(tracker.stored_cubes) == 2
    tracker.store_cubes([])
    assert len(tracker.stored_cubes) == 1
    tracker.store_cubes([])
    assert len(tracker.stored_cubes) == 0


def test_store_cubes() -> None:
    tracker = CubeTracker(average_position=False)

    tracker.store_cubes([Cube(Color.RED.name, Pose(Position(2, 0, 0))), Cube(Color.RED.name, Pose(Position(5, 0, 0)))])
    tracker.store_cubes(
        [
            Cube(Color.RED.name, Pose(Position(0, 0, 0))),
            Cube(Color.RED.name, Pose(Position(4, 0, 0))),
            Cube(Color.RED.name, Pose(Position(7, 0, 0))),
        ]
    )
    assert len(tracker.stored_cubes) == 3
    assert tracker.stored_cubes[0] == StoredCube(Cube(Color.RED.name, Pose(Position(0, 0, 0))), 0)
    assert tracker.stored_cubes[1] == StoredCube(Cube(Color.RED.name, Pose(Position(4, 0, 0))), 0)
    assert tracker.stored_cubes[2] == StoredCube(Cube(Color.RED.name, Pose(Position(7, 0, 0))), 0)
    tracker.stored_cubes = []

    tracker.store_cubes([Cube(Color.BLUE.name, Pose(Position(1, 0, 0)))])
    assert len(tracker.stored_cubes) == 1
    assert tracker.stored_cubes[0] == StoredCube(Cube(Color.BLUE.name, Pose(Position(1, 0, 0))), 0)

    tracker.store_cubes([Cube(Color.BLUE.name, Pose(Position(1, 1, 0)))])
    assert len(tracker.stored_cubes) == 1
    assert tracker.stored_cubes[0] == StoredCube(Cube(Color.BLUE.name, Pose(Position(1, 1, 0))), 0)

    tracker.store_cubes(
        [Cube(Color.BLUE.name, Pose(Position(1, 1, 0))), Cube(Color.BLUE.name, Pose(Position(0, 0, 5)))]
    )
    assert len(tracker.stored_cubes) == 2
    assert tracker.stored_cubes[0] == StoredCube(Cube(Color.BLUE.name, Pose(Position(1, 1, 0))), 0)
    assert tracker.stored_cubes[1] == StoredCube(Cube(Color.BLUE.name, Pose(Position(0, 0, 5))), 0)

    tracker.store_cubes([Cube(Color.BLUE.name, Pose(Position(0, 0, 3)))])
    assert len(tracker.stored_cubes) == 2
    assert tracker.stored_cubes[0] == StoredCube(Cube(Color.BLUE.name, Pose(Position(1, 1, 0))), 1)
    assert tracker.stored_cubes[1] == StoredCube(Cube(Color.BLUE.name, Pose(Position(0, 0, 3))), 0)

    tracker.average_position = True
    tracker.store_cubes([Cube(Color.BLUE.name, Pose(Position(1, 1, 1)))])
    assert tracker.stored_cubes[0] == StoredCube(Cube(Color.BLUE.name, Pose(Position(1, 1, 0.5))), 0)


def test_get_stored_cubes() -> None:
    tracker = CubeTracker()

    assert tracker.get_stored_cubes() == []

    pos1 = Pose(Position(5, 0, 0))
    pos2 = Pose(Position(1, 0, 0))

    tracker.stored_cubes = [
        StoredCube(Cube(Color.RED.name, pos1), 1),
        StoredCube(Cube(Color.GREEN.name, pos2), 0),
    ]

    assert tracker.get_stored_cubes() == [pos1, pos2]
    assert tracker.get_stored_cubes(Color.RED.name) == [pos1]
    assert tracker.get_stored_cubes(Color.YELLOW.name) == []


def test_get_cube_by_distance() -> None:
    tracker = CubeTracker()

    pos = [
        Pose(Position(0, 0, 0)),
        Pose(Position(1, 0, 0)),
        Pose(Position(2, 0, 0)),
        Pose(Position(0, 2, 0)),
        Pose(Position(0, 0, -3)),
        Pose(Position(5, 5, 5)),
    ]

    tracker.stored_cubes = [
        StoredCube(Cube(Color.RED.name, pos[0]), 1),
        StoredCube(Cube(Color.RED.name, pos[1]), 0),
        StoredCube(Cube(Color.RED.name, pos[2]), 0),
        StoredCube(Cube(Color.GREEN.name, pos[3]), 0),
        StoredCube(Cube(Color.GREEN.name, pos[4]), 0),
        StoredCube(Cube(Color.BLUE.name, pos[5]), 0),
    ]

    assert (
        tracker.get_cube_by_distance(
            distance_type=DistanceType.NEAREST,
            position=Position(0, 0, 0),
            offset=Position(0, 0, 0),
            max_distance=10,
            color=None,
        )
        == pos[0]
    )
    assert (
        tracker.get_cube_by_distance(
            distance_type=DistanceType.FARTHEST,
            position=Position(0, 0, 0),
            offset=Position(0, 0, 0),
            max_distance=10,
            color=None,
        )
        == pos[5]
    )
    assert (
        tracker.get_cube_by_distance(
            distance_type=DistanceType.FARTHEST,
            position=Position(0, 0, 0),
            offset=Position(0, 0, 0),
            max_distance=1.5,
            color=None,
        )
        == pos[1]
    )
    assert (
        tracker.get_cube_by_distance(
            distance_type=DistanceType.NEAREST,
            position=Position(0, 0, 0),
            offset=Position(0, 0, 0),
            max_distance=10,
            color=Color.GREEN.name,
        )
        == pos[3]
    )
    assert (
        tracker.get_cube_by_distance(
            distance_type=DistanceType.FARTHEST,
            position=Position(0, 0, 0),
            offset=Position(0, 0, 0),
            max_distance=10,
            color=Color.GREEN.name,
        )
        == pos[4]
    )
    assert (
        tracker.get_cube_by_distance(
            distance_type=DistanceType.NEAREST,
            position=Position(0, 0, 0),
            offset=Position(0, 0, 0),
            max_distance=10,
            color=Color.YELLOW.name,
        )
        is None
    )
    assert (
        tracker.get_cube_by_distance(
            distance_type=DistanceType.FARTHEST,
            position=Position(-2, 0, 0),
            offset=Position(0, 0, 0),
            max_distance=1,
            color=Color.RED.name,
        )
        is None
    )
    assert (
        tracker.get_cube_by_distance(
            distance_type=DistanceType.FARTHEST,
            position=Position(0, 0, 0),
            offset=Position(0, 0, 0),
            max_distance=10,
            color=Color.RED.name,
        )
        == pos[2]
    )
    assert tracker.get_cube_by_distance(
        distance_type=DistanceType.NEAREST,
        position=Position(0, 0, 0),
        offset=Position(5, 5, 5),
        max_distance=10,
        color=Color.RED.name,
    ) == Pose(Position(5, 5, 5))
