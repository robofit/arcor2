from arcor2_object_types.time_actions import TimeActions
from arcor2_object_types.utils import check_object_type


def test_time_actions() -> None:
    check_object_type(TimeActions)
    assert not TimeActions.abstract()
