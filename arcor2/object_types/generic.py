import abc
import copy
from typing import Dict, Optional

from arcor2 import CancelDict, DynamicParamDict
from arcor2.action import action
from arcor2.data.common import ActionMetadata, Pose, SceneObject
from arcor2.data.object_type import Models
from arcor2.docstring import parse_docstring
from arcor2.exceptions import Arcor2Exception


class GenericException(Arcor2Exception):
    pass


class Generic(metaclass=abc.ABCMeta):
    """
    Generic object
    """

    DYNAMIC_PARAMS: DynamicParamDict = {}
    CANCEL_MAPPING: CancelDict = {}

    def __init__(self, obj_id: str, name: str, pose: Pose, collision_model: Optional[Models] = None) -> None:

        self.id = obj_id
        self.name = name
        self.pose = pose
        self.collision_model = copy.deepcopy(collision_model)
        if self.collision_model:
            # originally, each model has id == object type (e.g. BigBox) but here we need to set it so something unique
            self.collision_model.id = self.id
        self._int_dict: Dict[str, int] = {}

    @classmethod
    def description(cls) -> str:  # TODO mixin with common stuff for objects/services?
        if not cls.__doc__:
            return "No description available."
        return parse_docstring(cls.__doc__)["short_description"]

    def scene_object(self) -> SceneObject:
        return SceneObject(self.id, self.name, self.__class__.__name__, self.pose)

    def __repr__(self) -> str:
        return str(self.__dict__)

    def cleanup(self) -> None:
        """
        This method is called when a scene is closed or when script ends.
        :return:
        """
        pass

    # TODO allow to store any value?
    @action
    def set_int(self, key: str, value: int) -> None:
        self._int_dict[key] = value

    @action
    def get_int(self, key: str) -> int:
        try:
            return self._int_dict[key]
        except KeyError:
            raise GenericException(f"Unknown key: {key}.")

    set_int.__action__ = ActionMetadata()  # type: ignore
    get_int.__action__ = ActionMetadata()  # type: ignore
