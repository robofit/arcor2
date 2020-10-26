from arcor2.object_types.utils import check_object_type
from arcor2_fit_demo.object_types.abstract_dobot import AbstractDobot


def test_abstract_dobot() -> None:
    check_object_type(AbstractDobot)
