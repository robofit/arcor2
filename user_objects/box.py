from arcor2.object_types import Generic
from arcor2.data import ActionMetadata
from arcor2.object_types.utils import action


class Box(Generic):

    @action
    def test(self) -> None:
        pass

    test.__action__ = ActionMetadata("test")
