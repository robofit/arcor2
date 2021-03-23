from ast import stmt
from typing import Any

from PIL.Image import Image

from arcor2.cached import CachedProject as CProject
from arcor2.cached import CachedScene as CScene
from arcor2.exceptions import Arcor2NotImplemented
from arcor2.image import image_from_json, image_to_json
from arcor2.parameter_plugins.base import ParameterPlugin, TypesDict


class ImagePlugin(ParameterPlugin):
    @classmethod
    def type(cls) -> Any:
        return Image

    @classmethod
    def type_name(cls) -> str:
        return "image"

    @classmethod
    def parameter_value(
        cls, type_defs: TypesDict, scene: CScene, project: CProject, action_id: str, parameter_id: str
    ) -> Image:
        json_str = super(ImagePlugin, cls).parameter_value(type_defs, scene, project, action_id, parameter_id)
        return cls._value_from_json(json_str)

    @classmethod
    def _value_from_json(cls, value: str) -> Image:
        return image_from_json(value)

    @classmethod
    def value_to_json(cls, value: Image) -> str:
        return image_to_json(value)

    @classmethod
    def parameter_ast(
        cls, type_defs: TypesDict, scene: CScene, project: CProject, action_id: str, parameter_id: str
    ) -> stmt:
        raise Arcor2NotImplemented("It does not make much sense to have image as literal.")
