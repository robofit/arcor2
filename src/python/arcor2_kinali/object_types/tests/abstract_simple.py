from arcor2.object_types.utils import check_object_type
from arcor2_kinali.object_types.abstract_simple import AbstractSimple


def test_abstract_simple() -> None:
    check_object_type(AbstractSimple)
