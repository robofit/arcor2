from arcor2.object_types.abstract import Robot
from arcor2.object_types.utils import check_object_type


def test_object_type() -> None:
    check_object_type(Robot)
    assert Robot.abstract()
