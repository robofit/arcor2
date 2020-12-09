from arcor2.object_types.utils import check_object_type
from arcor2.urdf import urdf_from_path
from arcor2_kinali import get_data
from arcor2_kinali.object_types.aubo import Aubo


def test_object_type() -> None:
    check_object_type(Aubo)
    assert not Aubo.abstract()


def test_urdf() -> None:
    urdf_from_path(get_data("aubo"))
