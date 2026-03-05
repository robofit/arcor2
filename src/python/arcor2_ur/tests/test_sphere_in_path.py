import math
import time

import pytest

from arcor2.data.common import Orientation, Pose, Position
from arcor2.data.object_type import Sphere
from arcor2_scene_data import scene_service
from arcor2_ur.object_types.ur5e import Ur5e, UrSettings
from arcor2_ur.tests.conftest import Urls


def _dist(a: Pose, b: Pose) -> float:
    dx = a.position.x - b.position.x
    dy = a.position.y - b.position.y
    dz = a.position.z - b.position.z
    return math.sqrt(dx * dx + dy * dy + dz * dz)


@pytest.mark.timeout(220)
def test_sphere_in_path(start_processes: Urls) -> None:
    scene_service.URL = start_processes.robot_url
    scene_service.start()
    assert scene_service.started()

    ot = Ur5e("", "", Pose(), UrSettings(start_processes.robot_url))
    assert len(ot.robot_joints()) == 6

    Y = 0.0
    Z = 0.2
    X = 0.9

    start_pose = Pose(Position(X, Y, Z), Orientation(0, 0, 0, 1))
    goal_pose = Pose(Position(Y, X, Z), Orientation(0, 0, 0, 1))
    ot.move_to_pose("", start_pose, 0.3, safe=False)

    sphere = Sphere("Sphere1", 0.09)
    scene_service.upsert_collision(sphere, Pose(Position(0.5, 0.5, 0.1), Orientation(0, 0, 0, 1)))
    assert sphere.id in scene_service.collision_ids()
    time.sleep(1)

    sphere = Sphere("Sphere2", 0.1)
    scene_service.upsert_collision(sphere, Pose(Position(0.5, 0.5, 0.3), Orientation(0, 0, 0, 1)))
    assert sphere.id in scene_service.collision_ids()
    time.sleep(1)

    sphere = Sphere("Sphere3", 0.09)
    scene_service.upsert_collision(sphere, Pose(Position(0.5, 0.5, 0.5), Orientation(0, 0, 0, 1)))
    assert sphere.id in scene_service.collision_ids()
    time.sleep(1)

    sphere = Sphere("Sphere4", 0.09)
    scene_service.upsert_collision(sphere, Pose(Position(-0.5, 0.5, 0.1), Orientation(0, 0, 0, 1)))
    assert sphere.id in scene_service.collision_ids()
    time.sleep(1)

    sphere = Sphere("Sphere5", 0.1)
    scene_service.upsert_collision(sphere, Pose(Position(-0.5, 0.5, 0.3), Orientation(0, 0, 0, 1)))
    assert sphere.id in scene_service.collision_ids()
    time.sleep(1)

    sphere = Sphere("Sphere6", 0.09)
    scene_service.upsert_collision(sphere, Pose(Position(-0.5, 0.5, 0.5), Orientation(0, 0, 0, 1)))
    assert sphere.id in scene_service.collision_ids()
    time.sleep(1)

    ot.move_to_pose("", goal_pose, 0.3)

    reached = ot.get_end_effector_pose("")
    assert _dist(reached, goal_pose) < 0.03

    scene_service.delete_all_collisions()
    ot.cleanup()
