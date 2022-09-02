import time
from typing import Optional

from arcor2.data.common import ActionMetadata, Pose
from arcor2.object_types.abstract import Generic


class ObjectReturningPose(Generic):

    _ABSTRACT = False

    def action_returning_pose(self, *, an: Optional[str] = None) -> Pose:
        return Pose()

    def action_taking_pose(self, param: Pose, *, an: Optional[str] = None) -> None:
        assert isinstance(param, Pose)
        time.sleep(0.1)

    action_returning_pose.__action__ = ActionMetadata()  # type: ignore
    action_taking_pose.__action__ = ActionMetadata()  # type: ignore
