import inspect

from arcor2.object_types.abstract import Robot
from arcor2.object_types.utils import check_object_type
from arcor2.urdf import urdf_from_path
from arcor2_kinali import get_data
from arcor2_kinali.object_types.aubo import Aubo


def test_signatures() -> None:

    assert inspect.signature(Robot.move_to_pose) == inspect.signature(Aubo.move_to_pose)
    assert inspect.signature(Robot.move_to_joints) == inspect.signature(Aubo.move_to_joints)
    assert inspect.signature(Robot.inverse_kinematics) == inspect.signature(Aubo.inverse_kinematics)
    assert inspect.signature(Robot.forward_kinematics) == inspect.signature(Aubo.forward_kinematics)
    assert inspect.signature(Robot.stop) == inspect.signature(Aubo.stop)
    assert inspect.signature(Robot.set_hand_teaching_mode) == inspect.signature(Aubo.set_hand_teaching_mode)


def test_object_type() -> None:
    check_object_type(Aubo)
    assert not Aubo.abstract()


def test_urdf() -> None:
    urdf_from_path(get_data("aubo"))
