from arcor2.object_types import Generic
from arcor2.action import action
from arcor2.data.common import ActionMetadata


class Tester(Generic):
    """
    A generic tester
    """

    @action
    def run_test(self) -> None:  # not needed in demo 0, just for test purposes
        pass

    run_test.__action__ = ActionMetadata(blocking=True)
