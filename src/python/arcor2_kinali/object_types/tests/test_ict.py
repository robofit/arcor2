from arcor2.object_types.utils import check_object_type
from arcor2_kinali.object_types.ict import Ict


def test_object_type() -> None:
    check_object_type(Ict)
    assert not Ict.abstract()
