import time

from arcor2.data.common import ActionMetadata, Pose
from arcor2.object_types.abstract import Generic


class ObjectReturningPose(Generic):
    _ABSTRACT = False

    def action_returning_pose(self, *, an: None | str = None) -> Pose:
        return Pose()

    def action_taking_pose(self, param: Pose, *, an: None | str = None) -> None:
        assert isinstance(param, Pose)
        time.sleep(0.1)

    action_returning_pose.__action__ = ActionMetadata()  # type: ignore
    action_taking_pose.__action__ = ActionMetadata()  # type: ignore
