import random
import time

from arcor2.data.common import ActionMetadata
from arcor2.object_types.abstract import CollisionObject


class MillingMachine(CollisionObject):
    _ABSTRACT = False

    def do_milling(self, *, an: None | str = None) -> bool:
        """Performs a (simulated) milling process. Returns False if something
        goes wrong.

        :param an:
        :return:
        """

        if random.uniform(0, 1) > 0.3:
            time.sleep(3)
            return True
        else:
            time.sleep(5)
            return False

    do_milling.__action__ = ActionMetadata()  # type: ignore
