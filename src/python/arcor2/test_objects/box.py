from arcor2.data.common import ActionMetadata
from arcor2.object_types.abstract import CollisionObject


class Box(CollisionObject):

    _ABSTRACT = False

    def test(self, *, an: None | str = None) -> None:
        """Run test.

        :return:
        """
        pass

    def action_with_unknown_parameter_type(self, param: ActionMetadata, *, an: None | str = None) -> bool:
        """Pointless action.

        :param param:
        :return:
        """
        return True

    test.__action__ = ActionMetadata()  # type: ignore
    action_with_unknown_parameter_type.__action__ = ActionMetadata()  # type: ignore
