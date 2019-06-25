from arcor2.core import WorldObject
from arcor2.data import ActionMetadata


class Tester(WorldObject):

    __DESCRIPTION__ = "A generic tester"

    def run_test(self) -> None:  # not needed in demo 0, just for test purposes
        pass

    run_test.__action__ = ActionMetadata(blocking=True)
