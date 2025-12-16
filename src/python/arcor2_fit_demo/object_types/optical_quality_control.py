import random
import time

from arcor2.data.common import ActionMetadata
from arcor2_object_types.abstract import GenericWithPose


class OpticalQualityControl(GenericWithPose):
    _ABSTRACT = False

    def measure_quality(self, *, an: None | str = None) -> bool:
        """Performs a (simulated) quality measurement. Returns False if
        something is wrong.

        :param an:
        :return:
        """

        time.sleep(0.01)
        return random.uniform(0, 1) > 0.3

    measure_quality.__action__ = ActionMetadata()  # type: ignore
