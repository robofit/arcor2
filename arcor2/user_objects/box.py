from arcor2.object_types import Generic
from arcor2.data.common import ActionMetadata
from arcor2.action import action


class Box(Generic):

    @action
    def test(self) -> None:
        pass

    test.__action__ = ActionMetadata()  # type: ignore
