from arcor2.object_types.utils import check_object_type
from arcor2_kinali.object_types.barcode import Barcode


def test_object_type() -> None:
    check_object_type(Barcode)
