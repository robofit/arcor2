import inspect

from arcor2.object_types.abstract import Robot
from arcor2.object_types.utils import check_object_type
from arcor2_fit_demo.object_types.abstract_dobot import AbstractDobot


def test_signatures() -> None:

    assert inspect.signature(Robot.move_to_pose) == inspect.signature(AbstractDobot.move_to_pose)
    assert inspect.signature(Robot.move_to_joints) == inspect.signature(AbstractDobot.move_to_joints)
    assert inspect.signature(Robot.inverse_kinematics) == inspect.signature(AbstractDobot.inverse_kinematics)
    assert inspect.signature(Robot.forward_kinematics) == inspect.signature(AbstractDobot.forward_kinematics)
    assert inspect.signature(Robot.stop) == inspect.signature(AbstractDobot.stop)
    assert inspect.signature(Robot.set_hand_teaching_mode) == inspect.signature(AbstractDobot.set_hand_teaching_mode)


def test_abstract_dobot() -> None:
    check_object_type(AbstractDobot)
    assert AbstractDobot.abstract()
