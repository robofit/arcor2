import time

from arcor2.data.common import ActionMetadata, Position
from arcor2.object_types.abstract import Generic


class PositionParam(Generic):

    _ABSTRACT = False

    def action_with_position_param(self, param: Position, *, an: None | str = None) -> None:
        """Pointless action.

        :param param:
        :return:
        """
        time.sleep(0.1)

    action_with_position_param.__action__ = ActionMetadata()  # type: ignore
