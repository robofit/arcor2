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
    def sleep(self, seconds: float) -> None:
        time.sleep(seconds)

    # TODO more "general" actions like store_value, get_value, etc.

    nop.__action__ = ActionMetadata()  # type: ignore
    sleep.__action__ = ActionMetadata(blocking=True)  # type: ignore
