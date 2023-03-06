import inspect

from arcor2.object_types.abstract import MultiArmRobot
from arcor2.object_types.tests.conftest import docstrings
from arcor2.object_types.utils import check_object_type
from arcor2_yumi.object_types.yumi import YuMi


def test_docstrings() -> None:
    docstrings(YuMi)


def test_signatures() -> None:
    assert inspect.signature(MultiArmRobot.move_to_pose) == inspect.signature(YuMi.move_to_pose)
    assert inspect.signature(MultiArmRobot.move_to_joints) == inspect.signature(YuMi.move_to_joints)
    assert inspect.signature(MultiArmRobot.inverse_kinematics) == inspect.signature(YuMi.inverse_kinematics)
    assert inspect.signature(MultiArmRobot.forward_kinematics) == inspect.signature(YuMi.forward_kinematics)
    assert inspect.signature(MultiArmRobot.stop) == inspect.signature(YuMi.stop)
    assert inspect.signature(MultiArmRobot.set_hand_teaching_mode) == inspect.signature(YuMi.set_hand_teaching_mode)


def test_abstract() -> None:
    check_object_type(YuMi)
    assert not YuMi.abstract()
