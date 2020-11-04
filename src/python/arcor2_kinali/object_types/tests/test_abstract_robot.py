from arcor2.object_types.utils import check_object_type
from arcor2_kinali.object_types.abstract_robot import AbstractRobot


def test_abstract_robot() -> None:
    check_object_type(AbstractRobot)
    assert AbstractRobot.abstract()
