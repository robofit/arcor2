from arcor2.data.common import ActionMetadata
from arcor2.object_types.abstract import Generic


class LogicActions(Generic):
    """Logic-related actions."""

    _ABSTRACT = False

    def equals(self, val1: int, val2: int, *, an: None | str = None) -> bool:
        """Tests if two integer values are equal.

        :param val1:
        :param val2:
        :return:
        """
        return val1 == val2

    def less_than(self, val1: int, val2: int, *, an: None | str = None) -> bool:
        """Compares two integer values.

        :param val1:
        :param val2:
        :return:
        """
        return val1 < val2

    def greater_than(self, val1: int, val2: int, *, an: None | str = None) -> bool:
        """Compares two integer values.

        :param val1:
        :param val2:
        :return:
        """
        return val1 > val2

    equals.__action__ = ActionMetadata()  # type: ignore
    less_than.__action__ = ActionMetadata()  # type: ignore
    greater_than.__action__ = ActionMetadata()  # type: ignore
