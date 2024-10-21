import inspect

from arcor2.object_types.abstract import Robot
from arcor2.object_types.tests.conftest import docstrings
from arcor2.object_types.utils import check_object_type
from arcor2_ur.object_types.ur5e import Ur5e


def test_docstrings() -> None:
    docstrings(Ur5e)


def test_signatures() -> None:
    assert inspect.signature(Robot.move_to_pose) == inspect.signature(Ur5e.move_to_pose)
    assert inspect.signature(Robot.move_to_joints) == inspect.signature(Ur5e.move_to_joints)
    assert inspect.signature(Robot.inverse_kinematics) == inspect.signature(Ur5e.inverse_kinematics)
    assert inspect.signature(Robot.forward_kinematics) == inspect.signature(Ur5e.forward_kinematics)
    assert inspect.signature(Robot.stop) == inspect.signature(Ur5e.stop)
    assert inspect.signature(Robot.set_hand_teaching_mode) == inspect.signature(Ur5e.set_hand_teaching_mode)


def test_ur5e() -> None:
    check_object_type(Ur5e)
    assert not Ur5e.abstract()
