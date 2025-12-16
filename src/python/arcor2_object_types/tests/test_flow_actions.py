from arcor2_object_types.flow_actions import FlowActions
from arcor2_object_types.utils import check_object_type


def test_flow_actions() -> None:
    check_object_type(FlowActions)
    assert not FlowActions.abstract()
