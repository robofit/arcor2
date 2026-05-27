import time

from arcor2.data.common import Orientation, Pose, Position
from arcor2.data.object_type import Cylinder
from arcor2_scene_data import scene_service
from arcor2_ur.common import EffectorType, GraspableState, GraspPosition
from arcor2_ur.object_types.ur5e import Ur5e, UrSettings
from arcor2_ur.tests.conftest import Urls


def test_pick_up_cylinder_by_position(start_processes: Urls) -> None:
    scene_service.URL = start_processes.robot_url
    scene_service.start()
    assert scene_service.started()

    ot = Ur5e("", "", Pose(), UrSettings(start_processes.robot_url))
    assert len(ot.robot_joints()) == 6

    X = 0.0
    Y = 0.5
    Z = 0.1

    object = Cylinder("Cyl1", 0.1, 0.2)
    scene_service.upsert_graspable(object, Pose(Position(X, Y, Z), Orientation(0, 0, 0, 1)), GraspableState.WORLD)
    time.sleep(1)

    ot.pick_up_object_by_position(Position(X, Y, Z), 0.5, EffectorType.SUCK, GraspPosition.TOP)

    assert ot.graspable_state(object.id) == GraspableState.ATTACHED

    scene_service.delete_all_collisions()
    ot.cleanup()
