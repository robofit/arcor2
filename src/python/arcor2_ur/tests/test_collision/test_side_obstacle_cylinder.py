import time

from arcor2.data.common import Orientation, Pose, Position
from arcor2.data.object_type import Cylinder
from arcor2_scene_data import scene_service
from arcor2_ur.object_types.ur5e import Ur5e, UrSettings
from arcor2_ur.tests.conftest import Urls


def test_side_cylinder(start_processes: Urls) -> None:
    scene_service.URL = start_processes.robot_url
    scene_service.start()
    assert scene_service.started()

    ot = Ur5e("", "", Pose(), UrSettings(start_processes.robot_url))
    assert len(ot.robot_joints()) == 6

    X = 0.5
    Y = 0.0
    Z = 0.3

    start_pose = Pose(Position(X, Y, Z), Orientation(1, 0, 0, 0))
    goal_pose = Pose(Position(Y, X, Z), Orientation(1, 0, 0, 0))
    ot.move_to_pose("", start_pose, 0.3, safe=False)

    cyl = Cylinder("Cyl1", 0.1, 0.95)
    scene_service.upsert_collision(cyl, Pose(Position(0.5, 0.5, 0.5), Orientation(0, 0, 0, 1)))
    assert cyl.id in scene_service.collision_ids()
    time.sleep(1)

    cyl = Cylinder("Cyl2", 0.1, 0.95)
    scene_service.upsert_collision(cyl, Pose(Position(-0.5, 0.5, 0.5), Orientation(0, 0, 0, 1)))
    assert cyl.id in scene_service.collision_ids()
    time.sleep(1)

    ot.move_to_pose("", goal_pose, 0.3)

    reached = ot.get_end_effector_pose("")
    assert goal_pose.position.distance(reached.position) < 0.03

    scene_service.delete_all_collisions()
    ot.cleanup()
