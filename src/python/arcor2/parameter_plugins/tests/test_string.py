import inspect
import json

import pytest

from arcor2.cached import CachedProject, CachedScene
from arcor2.data.common import Action, ActionParameter, ActionPoint, Position, Project, Scene, SceneObject
from arcor2.exceptions import Arcor2Exception
from arcor2.object_types.abstract import Generic
from arcor2.parameter_plugins import ParameterPluginException
from arcor2.parameter_plugins.string import StringPlugin
from arcor2.parameter_plugins.utils import plugin_from_instance, plugin_from_type


class TestObject(Generic):
    def action(self, arbitrary_type_param: str, str_param: int, some_other_param: int) -> None:
        pass


param_name = "str_param"


def test_abstract() -> None:
    assert not inspect.isabstract(StringPlugin)


def test_plugin_from_type() -> None:

    assert plugin_from_type(str) is StringPlugin


@pytest.mark.parametrize(
    "val",
    ["", "helloWorld"],
)
class TestParametrized:
    def test_plugin_from_instance(self, val: str) -> None:

        assert plugin_from_instance(val) is StringPlugin

    def test_value_to_json(self, val: str) -> None:

        assert StringPlugin.value_to_json(val) == json.dumps(val)

    def test_get_value(self, val: str) -> None:

        scene = Scene("s1")
        obj = SceneObject("test_name", TestObject.__name__)
        scene.objects.append(obj)
        project = Project("p1", "s1")
        ap1 = ActionPoint("ap1", Position())
        project.action_points.append(ap1)

        invalid_param_name = "invalid_param"

        ac1 = Action(
            "ac1",
            f"{obj.id}/{TestObject.action.__name__}",
            parameters=[
                ActionParameter(param_name, StringPlugin.type_name(), StringPlugin.value_to_json(val)),
                ActionParameter(invalid_param_name, StringPlugin.type_name(), json.dumps(666)),
            ],
        )

        ap1.actions.append(ac1)

        cscene = CachedScene(scene)
        cproject = CachedProject(project)

        with pytest.raises(Arcor2Exception):
            StringPlugin.parameter_value({}, cscene, cproject, ac1.id, "non_sense")

        with pytest.raises(Arcor2Exception):
            StringPlugin.parameter_value({}, cscene, cproject, "non_sense", param_name)

        with pytest.raises(ParameterPluginException):
            StringPlugin.parameter_value({}, cscene, cproject, ac1.id, invalid_param_name)

        value = StringPlugin.parameter_value({}, cscene, cproject, ac1.id, param_name)
        exe_value = StringPlugin.parameter_execution_value({}, cscene, cproject, ac1.id, param_name)

        assert value == val
        assert value == exe_value
