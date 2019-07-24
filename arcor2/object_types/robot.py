import time

from arcor2.object_types.generic import Generic
from arcor2.object_types_utils import action
from arcor2.data import ActionMetadata, ActionPoint


class Robot(Generic):
    """
    Abstract class representing robot and its basic capabilities (motion)
    """

    @action
    def move_to(self, target: ActionPoint, end_effector: str, speed: int) -> None:

        # TODO action point pose should be relative to its parent object pose - how and where to get the absolute pose?

        # TODO call underlying API
        time.sleep(1)
        return

    move_to.__action__ = ActionMetadata(free=True, blocking=True)  # type: ignore
