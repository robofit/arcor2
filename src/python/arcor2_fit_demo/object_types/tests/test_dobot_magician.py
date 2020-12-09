from arcor2.object_types.utils import check_object_type
from arcor2.urdf import urdf_from_path
from arcor2_fit_demo import get_data
from arcor2_fit_demo.object_types.dobot_magician import DobotMagician


def test_dobot_magician() -> None:
    check_object_type(DobotMagician)
    assert not DobotMagician.abstract()


def test_urdf() -> None:
    urdf_from_path(get_data("dobot-magician"))
