from arcor2.action import action
from arcor2.data.common import ActionMetadata
from arcor2.object_types.abstract import Generic


class LogicActions(Generic):
    """
    Logic-related actions.
    """

    @action
    def equals(self, val1: int, val2: int) -> bool:
        return val1 == val2

    @action
    def less_than(self, val1: int, val2: int) -> bool:
        return val1 < val2

    @action
    def greater_than(self, val1: int, val2: int) -> bool:
        return val1 > val2

    equals.__action__ = ActionMetadata(blocking=True)  # type: ignore
    less_than.__action__ = ActionMetadata(blocking=True)  # type: ignore
    greater_than.__action__ = ActionMetadata(blocking=True)  # type: ignore
