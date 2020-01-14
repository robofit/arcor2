import abc
from typing import Dict, Optional
import time

from arcor2 import DynamicParamDict
from arcor2.data.common import Pose, ActionPoint, ActionMetadata, SceneObject
from arcor2.action import action
from arcor2.data.object_type import Models
from arcor2.docstring import parse_docstring


class Generic(metaclass=abc.ABCMeta):
    """
    Generic object
    """

    DYNAMIC_PARAMS: DynamicParamDict = {}

    def __init__(self, obj_id: str, pose: Pose, collision_model: Optional[Models] = None) -> None:

        self.id = obj_id
        self.pose = pose
        self.collision_model = collision_model
        self.action_points: Dict[str, ActionPoint] = {}
        self._rate_start_time: Optional[float] = None

    @classmethod
    def description(cls) -> str:  # TODO mixin with common stuff for objects/services?
        return parse_docstring(cls.__doc__)["short_description"]

    def scene_object(self) -> SceneObject:
        return SceneObject(self.id, self.__class__.__name__, self.pose)

    def __repr__(self) -> str:
        return str(self.__dict__)

    @action
    def nop(self) -> None:
        pass

    @action
    def sleep(self, seconds: float = 1.0) -> None:

        assert 0.0 <= seconds <= 10.0e6

        time.sleep(seconds)

    @action
    def rate(self, period: float = 1.0) -> None:
        """
        Can be used to maintain desired rate of the loop. Should be the first action.
        :param period: Desired period in seconds.
        :return:
        """

        assert 0.0 <= period <= 10.0e6

        now = time.monotonic()

        if self._rate_start_time is None:
            self._rate_start_time = now
            return

        dif = self._rate_start_time + period - now

        if dif > 0:
            time.sleep(dif)

    # TODO more "general" actions like store_value, get_value, etc.
    nop.__action__ = ActionMetadata()  # type: ignore
    sleep.__action__ = ActionMetadata(blocking=True)  # type: ignore
    rate.__action__ = ActionMetadata(blocking=True)  # type: ignore
