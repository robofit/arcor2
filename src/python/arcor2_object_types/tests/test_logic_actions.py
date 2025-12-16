from arcor2_object_types.logic_actions import LogicActions
from arcor2_object_types.utils import check_object_type


def test_logic_actions() -> None:
    check_object_type(LogicActions)
    assert not LogicActions.abstract()
