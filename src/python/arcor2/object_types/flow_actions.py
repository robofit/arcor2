from arcor2.data.common import ActionMetadata
from arcor2.object_types.abstract import Generic, Settings


class FlowActions(Generic):
    """Provides actions related to program flow."""

    _ABSTRACT = False

    def __init__(self, obj_id: str, name: str, settings: None | Settings = None) -> None:
        super().__init__(obj_id, name, settings)
        self._first_pass = True

    def is_first_pass(self, *, an: None | str = None) -> bool:
        """Returns True for the first pass of the main cycle.

        :param an:
        :return:
        """

        if ret := self._first_pass:
            self._first_pass = False

        return ret

    is_first_pass.__action__ = ActionMetadata()  # type: ignore
