from arcor2.data.common import ActionMetadata
from arcor2.object_types.abstract import GenericWithPose


class Box(GenericWithPose):

    _ABSTRACT = False

    def test(self) -> None:
        """Run test.

        :return:
        """
        pass

    def action_with_unknown_parameter_type(self, param: ActionMetadata) -> bool:
        """Pointless action.

        :param param:
        :return:
        """
        return True

    test.__action__ = ActionMetadata()  # type: ignore
    action_with_unknown_parameter_type.__action__ = ActionMetadata()  # type: ignore
