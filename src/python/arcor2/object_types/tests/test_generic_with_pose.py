from arcor2.object_types.abstract import GenericWithPose
from arcor2.object_types.utils import check_object_type


def test_object_type() -> None:
    check_object_type(GenericWithPose)
    assert GenericWithPose.abstract()
