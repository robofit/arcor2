import inspect

from arcor2.object_types.abstract import Robot
from arcor2.object_types.utils import check_object_type
from arcor2_kinali.object_types.abstract_robot import AbstractRobot


def test_signatures() -> None:

    assert inspect.signature(Robot.move_to_pose) == inspect.signature(AbstractRobot.move_to_pose)
    assert inspect.signature(Robot.move_to_joints) == inspect.signature(AbstractRobot.move_to_joints)
    assert inspect.signature(Robot.inverse_kinematics) == inspect.signature(AbstractRobot.inverse_kinematics)
    assert inspect.signature(Robot.forward_kinematics) == inspect.signature(AbstractRobot.forward_kinematics)
    assert inspect.signature(Robot.stop) == inspect.signature(AbstractRobot.stop)
    assert inspect.signature(Robot.set_hand_teaching_mode) == inspect.signature(AbstractRobot.set_hand_teaching_mode)


def test_abstract_robot() -> None:
    check_object_type(AbstractRobot)
    assert AbstractRobot.abstract()

    assert inspect.signature(AbstractRobot.move_to_joints) == inspect.signature(Robot.move_to_joints)
