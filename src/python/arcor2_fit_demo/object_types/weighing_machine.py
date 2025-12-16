import random
import time

from arcor2.data.common import ActionMetadata
from arcor2_object_types.abstract import CollisionObject


class WeighingMachine(CollisionObject):
    _ABSTRACT = False

    def check_weight(self, required: float = 1.0, max_diff: float = 0.1, *, an: None | str = None) -> bool:
        """Returns true if weight of an object being measured is within.

        <required-max_diff, required+max_diff>.

        :param required: Required (target) weight.
        :param max_diff: Maximal allowed difference.
        :param an:
        :return: True if object weight is OK.
        """

        if random.uniform(0, 1) > 0.3:
            time.sleep(1)
            return True
        else:
            time.sleep(1)
            return False

    check_weight.__action__ = ActionMetadata()  # type: ignore
