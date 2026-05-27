import time

from arcor2.data.common import Orientation, Pose, Position
from arcor2.data.object_type import Sphere
from arcor2_scene_data import scene_service
from arcor2_ur.common import EffectorType, GraspableState, GraspPosition
from arcor2_ur.object_types.ur5e import Ur5e, UrSettings
from arcor2_ur.tests.conftest import Urls


def test_pick_and_place_sphere_by_id(start_processes: Urls) -> None:
    scene_service.URL = start_processes.robot_url
    scene_service.start()
    assert scene_service.started()

    ot = Ur5e("", "", Pose(), UrSettings(start_processes.robot_url))
    assert len(ot.robot_joints()) == 6

    X = 0.0
    Y = 0.5
    Z = 0.1

    object = Sphere("Sphere1", 0.1)
    scene_service.upsert_graspable(object, Pose(Position(X, Y, Z), Orientation(0, 0, 0, 1)), GraspableState.WORLD)
    time.sleep(1)

    ot.pick_up_object_by_id(object.id, EffectorType.SUCK, GraspPosition.TOP)

    assert ot.graspable_state(object.id) == GraspableState.ATTACHED

    ot.place_object(Pose(Position(Y, X, Z), Orientation(0, 0, 0, 1)))

    assert Position(Y, X, Z).distance(ot.graspable_position(object.id)) < 0.03
    assert ot.graspable_state(object.id) == GraspableState.WORLD

    scene_service.delete_all_collisions()
    ot.cleanup()
