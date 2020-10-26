from arcor2.object_types.utils import check_object_type
from arcor2_kinali.object_types.search import Search


def test_object_type() -> None:
    check_object_type(Search)
