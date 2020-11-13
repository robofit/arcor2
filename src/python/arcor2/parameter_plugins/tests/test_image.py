import inspect
import json
from typing import Dict, Type

import pytest  # type: ignore
from PIL import Image  # type: ignore

from arcor2.cached import CachedProject, CachedScene
from arcor2.data.common import Action, ActionParameter, ActionPoint, Position, Project, Scene, SceneObject
from arcor2.exceptions import Arcor2Exception
from arcor2.object_types.abstract import Generic
from arcor2.parameter_plugins import ParameterPluginException
from arcor2.parameter_plugins.image import ImagePlugin
from arcor2.parameter_plugins.utils import plugin_from_instance, plugin_from_type


class TestObject(Generic):
    def action(self, arbitrary_type_param: str, image_param: Image.Image, some_other_param: int) -> None:
        pass


param_name = "image_param"
type_defs: Dict[str, Type[Generic]] = {TestObject.__name__: TestObject}


def test_abstract() -> None:
    assert not inspect.isabstract(ImagePlugin)


def test_plugin_from_type() -> None:

    assert plugin_from_type(Image.Image) is ImagePlugin


def test_plugin_from_instance() -> None:

    assert plugin_from_instance(Image.new("RGB", (320, 240))) is ImagePlugin


@pytest.mark.xfail(reason="Image plugin is currently broken.")
def test_get_value() -> None:

    img = Image.new("RGB", (320, 240))

    scene = Scene("s1", "s1")
    obj_id = "TestId"
    scene.objects.append(SceneObject(obj_id, "test_name", TestObject.__name__))
    project = Project("p1", "p1", "s1")
    ap1 = ActionPoint("ap1", "ap1", Position(1, 0, 0))
    project.action_points.append(ap1)

    invalid_param_name = "invalid_param"
    action_id = "ac1"

    ap1.actions.append(
        Action(
            action_id,
            action_id,
            f"{obj_id}/{TestObject.action.__name__}",
            [
                ActionParameter(param_name, ImagePlugin.type_name(), ImagePlugin.value_to_json(img)),
                ActionParameter(invalid_param_name, ImagePlugin.type_name(), json.dumps("non_sense")),
            ],
        )
    )

    cscene = CachedScene(scene)
    cproject = CachedProject(project)

    with pytest.raises(Arcor2Exception):
        ImagePlugin.parameter_value(type_defs, cscene, cproject, action_id, "non_sense")

    with pytest.raises(Arcor2Exception):
        ImagePlugin.parameter_value(type_defs, cscene, cproject, "non_sense", param_name)

    with pytest.raises(ParameterPluginException):
        ImagePlugin.parameter_value(type_defs, cscene, cproject, action_id, invalid_param_name)

    value = ImagePlugin.parameter_value(type_defs, cscene, cproject, action_id, param_name)
    exe_value = ImagePlugin.parameter_execution_value(type_defs, cscene, cproject, action_id, param_name)

    assert value == value
    assert value == exe_value
