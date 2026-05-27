from arcor2.data.common import Pose
from arcor2_scene_data import scene_service
from arcor2_ur.object_types.ur5e import Ur5e, UrSettings
from arcor2_ur.scripts.robot_publisher import load_robot_description
from arcor2_ur.tests.conftest import Urls


def test_suck_effector(start_processes: Urls) -> None:

    robot_description = load_robot_description()
    assert "suction_base_link" in robot_description
    assert "suction_cup_link" in robot_description
    assert "suction_tcp" in robot_description
    assert "tool0_to_suction_base" in robot_description
    assert "suction_base_to_cup" in robot_description
    assert "suction_cup_to_tcp" in robot_description

    scene_service.URL = start_processes.robot_url
    scene_service.start()
    assert scene_service.started()

    ot = Ur5e("", "", Pose(), UrSettings(start_processes.robot_url))

    assert len(ot.robot_joints()) == 6

    pos = ot.get_end_effector_pose("")
    orig_z = pos.position.z
    pos.position.z -= 0.05
    ot.move_to_pose("", pos, 0.5)
    pos_after = ot.get_end_effector_pose("")
    assert orig_z - pos_after.position.z > 0.035

    ot.cleanup()
