import time

import pytest

from arcor2.data.common import Orientation, Pose, Position
from arcor2.data.object_type import Box
from arcor2.exceptions import Arcor2Exception
from arcor2_scene_data import scene_service
from arcor2_ur.common import EffectorType, GraspableState, GraspPosition
from arcor2_ur.object_types.ur5e import Ur5e, UrSettings
from arcor2_ur.tests.conftest import Urls


def test_pick_and_move_wall(start_processes: Urls) -> None:
    scene_service.URL = start_processes.robot_url
    scene_service.start()
    assert scene_service.started()

    ot = Ur5e("", "", Pose(), UrSettings(start_processes.robot_url))
    assert len(ot.robot_joints()) == 6

    X = 0.0
    Y = 0.5
    Z = 0.1

    object = Box("Box1", 0.2, 0.2, 0.2)
    scene_service.upsert_graspable(object, Pose(Position(X, Y, Z), Orientation(0, 0, 0, 1)), GraspableState.WORLD)
    time.sleep(1)

    ot.pick_up_object_by_id(object.id, EffectorType.SUCK, GraspPosition.TOP)
    assert ot.graspable_state(object.id) == GraspableState.ATTACHED

    box = Box("Wall1", 0.1, 2.0, 1.0)
    scene_service.upsert_collision(box, Pose(Position(0.4, 0.0, 0.5), Orientation(0, 0, 0, 1)))
    assert box.id in scene_service.collision_ids()
    time.sleep(1)

    with pytest.raises(Arcor2Exception):
        ot.move_to_pose("", Pose(Position(Y, X, Z), Orientation(0, 0, 0, 1)), 0.3)

    scene_service.delete_all_collisions()
    ot.cleanup()
