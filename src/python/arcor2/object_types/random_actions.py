import random

from arcor2.data.common import ActionMetadata
from arcor2.exceptions import Arcor2Exception
from arcor2.object_types.abstract import Generic


class RandomActions(Generic):
    """Collection of actions to generate random values."""

    _ABSTRACT = False

    def random_integer(self, range_min: int, range_max: int, *, an: None | str = None) -> int:
        """Generates random integer in given range (including min/max values).

        :param range_min: Minimal value.
        :param range_max: Maximal value.
        :return:
        """

        try:
            return random.randint(range_min, range_max)
        except ValueError as e:
            raise Arcor2Exception(str(e)) from e

    def random_double(self, range_min: float, range_max: float, *, an: None | str = None) -> float:
        """Generates random double in given range.

        :param range_min: Minimal value.
        :param range_max: Maximal value.
        :return:
        """

        try:
            return random.uniform(range_min, range_max)
        except ValueError as e:
            raise Arcor2Exception(str(e)) from e

    def random_bool(self, *, an: None | str = None) -> bool:
        """Returns random boolean value.

        :return:
        """
        return random.choice((False, True))

    random_integer.__action__ = ActionMetadata()  # type: ignore
    random_double.__action__ = ActionMetadata()  # type: ignore
    random_bool.__action__ = ActionMetadata()  # type: ignore
