import inspect
import json

import pytest

from arcor2.cached import CachedProject, CachedScene
from arcor2.data.common import Action, ActionParameter, ActionPoint, Position, Project, Scene, SceneObject
from arcor2.exceptions import Arcor2Exception
from arcor2.object_types.abstract import Generic
from arcor2.parameter_plugins import ParameterPluginException
from arcor2.parameter_plugins.boolean import BooleanPlugin
from arcor2.parameter_plugins.utils import plugin_from_instance, plugin_from_type


class TestObject(Generic):
    def action(self, arbitrary_type_param: str, bool_param: bool, some_other_param: int) -> None:
        pass


def test_abstract() -> None:
    assert not inspect.isabstract(BooleanPlugin)


def test_plugin_from_type() -> None:

    assert plugin_from_type(bool) is BooleanPlugin


@pytest.mark.parametrize(
    "val",
    [False, True],
)
class TestParametrized:
    def test_plugin_from_instance(self, val: bool) -> None:

        assert plugin_from_instance(val) is BooleanPlugin

    def test_value_to_json(self, val: bool) -> None:

        assert BooleanPlugin.value_to_json(val) == json.dumps(val)

    def test_get_value(self, val: bool) -> None:

        scene = Scene("s1", "s1")
        obj_id = "TestId"
        scene.objects.append(SceneObject(obj_id, "test_name", TestObject.__name__))
        project = Project("p1", "p1", "s1")
        ap1 = ActionPoint("ap1", "ap1", Position())
        project.action_points.append(ap1)

        param_name = "bool_param"
        invalid_param_name = "invalid_param"
        action_id = "ac1"

        ap1.actions.append(
            Action(
                action_id,
                action_id,
                f"{obj_id}/{TestObject.action.__name__}",
                [
                    ActionParameter(param_name, BooleanPlugin.type_name(), BooleanPlugin.value_to_json(val)),
                    ActionParameter(invalid_param_name, BooleanPlugin.type_name(), json.dumps("non_sense")),
                ],
            )
        )

        cscene = CachedScene(scene)
        cproject = CachedProject(project)

        with pytest.raises(Arcor2Exception):
            BooleanPlugin.parameter_value({}, cscene, cproject, action_id, "non_sense")

        with pytest.raises(Arcor2Exception):
            BooleanPlugin.parameter_value({}, cscene, cproject, "non_sense", param_name)

        with pytest.raises(ParameterPluginException):
            BooleanPlugin.parameter_value({}, cscene, cproject, action_id, invalid_param_name)

        value = BooleanPlugin.parameter_value({}, cscene, cproject, action_id, param_name)
        exe_value = BooleanPlugin.parameter_execution_value({}, cscene, cproject, action_id, param_name)

        assert value == val
        assert value == exe_value
