import inspect

from arcor2.object_types.abstract import Robot
from arcor2.object_types.utils import check_object_type
from arcor2.urdf import urdf_from_path
from arcor2_fit_demo import get_data
from arcor2_fit_demo.object_types.dobot_m1 import DobotM1


def test_signatures() -> None:

    assert inspect.signature(Robot.move_to_pose) == inspect.signature(DobotM1.move_to_pose)
    assert inspect.signature(Robot.move_to_joints) == inspect.signature(DobotM1.move_to_joints)
    assert inspect.signature(Robot.inverse_kinematics) == inspect.signature(DobotM1.inverse_kinematics)
    assert inspect.signature(Robot.forward_kinematics) == inspect.signature(DobotM1.forward_kinematics)
    assert inspect.signature(Robot.stop) == inspect.signature(DobotM1.stop)
    assert inspect.signature(Robot.set_hand_teaching_mode) == inspect.signature(DobotM1.set_hand_teaching_mode)


def test_dobot_m1() -> None:
    check_object_type(DobotM1)
    assert not DobotM1.abstract()

    assert inspect.signature(DobotM1.set_hand_teaching_mode) == inspect.signature(Robot.set_hand_teaching_mode)


def test_urdf() -> None:
    urdf_from_path(get_data("dobot-m1"))
