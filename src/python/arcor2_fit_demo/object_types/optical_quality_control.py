import random
import time

from arcor2.data.common import ActionMetadata
from arcor2.object_types.abstract import CollisionObject


class OpticalQualityControl(CollisionObject):
    mesh_filename = "kinect_azure.dae"
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
