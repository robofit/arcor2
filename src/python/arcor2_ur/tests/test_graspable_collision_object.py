import time

import pytest

from arcor2.data.common import Orientation, Pose, Position
from arcor2.data.object_type import Cylinder
from arcor2_object_types.abstract import GraspableSource, GraspableState
from arcor2_scene_data import scene_service
from arcor2_ur.object_types.ur5e import Ur5e, UrSettings
from arcor2_ur.tests.conftest import Urls


@pytest.mark.timeout(321)
def test_graspable_collision_object(start_processes: Urls) -> None:
    scene_service.URL = start_processes.robot_url
    scene_service.start()
    assert scene_service.started()

    ot = Ur5e("", "", Pose(), UrSettings(start_processes.robot_url))
    assert len(ot.robot_joints()) == 6

    y = 0.0
    z = 0.2
    x = 0.9

    start_pose = Pose(Position(x, y, z), Orientation(0, 0, 0, 1))
    goal_pose = Pose(Position(y, x, z), Orientation(0, 0, 0, 1))
    ot.move_to_pose("", start_pose, 0.3, safe=False)

    cyl1 = Cylinder("Cyl1", 0.1, 0.95)
    scene_service.upsert_graspable(
        cyl1, Pose(Position(0.5, 0.5, 0.5), Orientation(0, 0, 0, 1)), state=GraspableState.WORLD
    )
    assert cyl1.id in scene_service.collision_ids()
    time.sleep(1)

    cyl2 = Cylinder("Cyl2", 0.1, 0.95)
    scene_service.upsert_collision(cyl2, Pose(Position(-0.5, 0.5, 0.5), Orientation(0, 0, 0, 1)))
    assert cyl2.id in scene_service.collision_ids()
    time.sleep(1)

    cyl3 = Cylinder("Cyl3", 0.1, 0.95)
    scene_service.upsert_graspable(
        cyl3,
        Pose(Position(0.0, 0.0, 0.0), Orientation(0, 0, 0, 1)),
        state=GraspableState.ATTACHED,
        source=GraspableSource.OTHER,
    )
    assert cyl3.id in scene_service.collision_ids()
    time.sleep(1)

    ot.move_to_pose("", goal_pose, 0.3)

    reached = ot.get_end_effector_pose("")
    assert goal_pose.position.distance(reached.position) < 0.03

    scene_service.delete_all_collisions()

    ot.cleanup()
