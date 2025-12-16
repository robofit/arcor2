import inspect

from arcor2_fit_demo import get_data
from arcor2_fit_demo.object_types.dobot_magician import DobotMagician
from arcor2_object_types.abstract import Robot
from arcor2_object_types.tests.conftest import docstrings
from arcor2_object_types.utils import check_object_type
from arcor2_urdf_utils.urdf import urdf_from_path


def test_docstrings() -> None:
    docstrings(DobotMagician)


def test_signatures() -> None:
    assert inspect.signature(Robot.move_to_pose) == inspect.signature(DobotMagician.move_to_pose)
    assert inspect.signature(Robot.move_to_joints) == inspect.signature(DobotMagician.move_to_joints)
    assert inspect.signature(Robot.inverse_kinematics) == inspect.signature(DobotMagician.inverse_kinematics)
    assert inspect.signature(Robot.forward_kinematics) == inspect.signature(DobotMagician.forward_kinematics)
    assert inspect.signature(Robot.stop) == inspect.signature(DobotMagician.stop)
    assert inspect.signature(Robot.set_hand_teaching_mode) == inspect.signature(DobotMagician.set_hand_teaching_mode)


def test_dobot_magician() -> None:
    check_object_type(DobotMagician)
    assert not DobotMagician.abstract()


def test_urdf() -> None:
    urdf_from_path(get_data("dobot-magician"))
