from arcor2.object_types.utils import check_object_type
from arcor2_kinali.object_types.statistic import Statistic


def test_object_type() -> None:
    check_object_type(Statistic)
