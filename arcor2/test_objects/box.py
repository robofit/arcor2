from arcor2.action import action
from arcor2.data.common import ActionMetadata
from arcor2.object_types.abstract import GenericWithPose


class Box(GenericWithPose):

    @action
    def test(self) -> None:
        pass

    @action
    def action_with_unknown_parameter_type(self, param: ActionMetadata) -> bool:
        return True

    test.__action__ = ActionMetadata()  # type: ignore
    action_with_unknown_parameter_type.__action__ = ActionMetadata()  # type: ignore
