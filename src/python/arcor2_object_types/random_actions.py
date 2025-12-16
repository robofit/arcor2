import random

from arcor2.data.common import ActionMetadata
from arcor2_object_types.abstract import Generic


class RandomActions(Generic):
    """Provides actions related to randomness."""

    _ABSTRACT = False

    def random_int(self, range_min: int = 0, range_max: int = 100, *, an: None | str = None) -> int:
        """Returns a random integer in a given range."""

        return random.randint(range_min, range_max)

    def random_double(self, range_min: float = 0.0, range_max: float = 1.0, *, an: None | str = None) -> float:
        """Returns a random float in a given range."""

        return random.uniform(range_min, range_max)

    def random_bool(self, probability: float = 0.5, *, an: None | str = None) -> bool:
        """Returns True with the given probability (0-1)."""

        return random.random() < probability

    random_int.__action__ = ActionMetadata()  # type: ignore
    random_double.__action__ = ActionMetadata()  # type: ignore
    random_bool.__action__ = ActionMetadata()  # type: ignore
