from typing import FrozenSet

from arcor2.services import Service
from arcor2.data.common import ActionMetadata
from arcor2.action import action


class LogicService(Service):
    """
    Logic-related actions.
    """

    def __init__(self, configuration_id: str):  # TODO avoid need for configuration_id?
        super(LogicService, self).__init__(configuration_id)

    @staticmethod
    def get_configuration_ids() -> FrozenSet[str]:
        return frozenset({"default"})

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
