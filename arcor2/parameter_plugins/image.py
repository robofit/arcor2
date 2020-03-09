import base64
import io

from PIL.Image import Image  # type: ignore
import PIL.Image  # type: ignore

from arcor2.data.common import Project, Scene
from arcor2.parameter_plugins.base import ParameterPlugin, TypesDict


class ImagePlugin(ParameterPlugin):

    @classmethod
    def type(cls):
        return Image

    @classmethod
    def type_name(cls) -> str:
        return "image"

    @classmethod
    def value(cls, type_defs: TypesDict, scene: Scene, project: Project, action_id: str, parameter_id: str) -> Image:
        json_str = super(ImagePlugin, cls).value(type_defs, scene, project, action_id, parameter_id)
        b64_bytes = json_str.encode()
        image_data = base64.b64decode(b64_bytes)
        return PIL.Image.open(io.BytesIO(image_data))

    @classmethod
    def value_to_json(cls, value: Image) -> str:
        b64_bytes = base64.b64encode(value.tobytes())
        b64_str = b64_bytes.decode()
        return b64_str
