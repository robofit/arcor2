from arcor2.object_types.utils import check_object_type
from arcor2_kinali.object_types.abstract_with_pose import AbstractWithPose


def test_object_type() -> None:
    check_object_type(AbstractWithPose)
