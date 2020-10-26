from arcor2.object_types.utils import check_object_type
from arcor2_fit_demo.object_types.dobot_magician import DobotMagician


def test_dobot_magician() -> None:
    check_object_type(DobotMagician)
