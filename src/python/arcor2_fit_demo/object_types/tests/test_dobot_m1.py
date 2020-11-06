from arcor2.object_types.utils import check_object_type
from arcor2_fit_demo.object_types.dobot_m1 import DobotM1


def test_dobot_m1() -> None:
    check_object_type(DobotM1)
    assert not DobotM1.abstract()
