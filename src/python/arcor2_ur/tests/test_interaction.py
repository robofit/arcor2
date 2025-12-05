import time

import pytest

from arcor2.clients import scene_service
from arcor2.data.common import Orientation, Pose, Position
from arcor2.data.object_type import Box
from arcor2.exceptions import Arcor2Exception
from arcor2_ur.object_types.ur5e import Ur5e, UrSettings
from arcor2_ur.tests.conftest import Urls


@pytest.mark.timeout(60)
def test_basics(start_processes: Urls) -> None:
    scene_service.URL = start_processes.robot_url
    box = Box("UniqueBoxId", 0.1, 0.1, 0.1)
    scene_service.upsert_collision(box, Pose(Position(1, 0, 0), Orientation(0, 0, 0, 1)))
    scene_service.start()
    assert scene_service.started()

    ot = Ur5e("", "", Pose(), UrSettings(start_processes.robot_url))

    assert len(ot.robot_joints()) == 6
    pos = ot.get_end_effector_pose("")
    orig_z = pos.position.z
    pos.position.z -= 0.05
    ot.move_to_pose("", pos, 0.5)
    pos_after = ot.get_end_effector_pose("")
    assert orig_z - pos_after.position.z > 0.045

    ot.suck()
    ot.release()

    assert scene_service.collision_ids() == {box.id}

    scene_service.upsert_collision(box, pos)
    pos.position.z += 0.01
    with pytest.raises(Arcor2Exception):  # attempt to move into a collision object
        ot.move_to_pose("", pos, 0.5)

    # now without collision checking
    ot.move_to_pose("", pos, 0.5, safe=False)

    pos.position.z -= 0.01
    with pytest.raises(Arcor2Exception):  # start state in collision
        ot.move_to_pose("", pos, 0.5)

    scene_service.delete_all_collisions()
    assert not scene_service.collision_ids()

    ot.move_to_pose("", pos, 0.5)

    assert not ot.get_hand_teaching_mode()

    ot.set_hand_teaching_mode(True)
    assert ot.get_hand_teaching_mode()
    time.sleep(0.5)
    assert ot.get_hand_teaching_mode()

    ot.set_hand_teaching_mode(False)
    assert not ot.get_hand_teaching_mode()

    ot.cleanup()
