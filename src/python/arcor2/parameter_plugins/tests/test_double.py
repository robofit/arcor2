import inspect
import json

import pytest  # type: ignore

from arcor2.cached import CachedProject, CachedScene
from arcor2.data.common import Action, ActionParameter, ActionPoint, Position, Project, Scene, SceneObject
from arcor2.data.object_type import ParameterMeta
from arcor2.exceptions import Arcor2Exception
from arcor2.object_types.abstract import Generic
from arcor2.parameter_plugins import ParameterPluginException
from arcor2.parameter_plugins.double import DoublePlugin
from arcor2.parameter_plugins.integer import IntegerParameterExtra
from arcor2.parameter_plugins.utils import plugin_from_instance, plugin_from_type
from arcor2.source.utils import find_function, parse_def


class TestObject(Generic):
    def action(self, arbitrary_type_param: str, double_param: float, some_other_param: int) -> None:

        assert 0.0 <= double_param <= 1.0


param_name = "double_param"


def test_abstract() -> None:
    assert not inspect.isabstract(DoublePlugin)


def test_plugin_from_type() -> None:

    assert plugin_from_type(float) is DoublePlugin


def test_meta() -> None:

    meta = ParameterMeta(param_name, DoublePlugin.type_name())
    DoublePlugin.meta(meta, TestObject.action, find_function(TestObject.action.__name__, parse_def(TestObject)))
    assert meta.extra

    extra = IntegerParameterExtra.from_json(meta.extra)

    assert extra.minimum == 0
    assert extra.maximum == 1


@pytest.mark.parametrize(
    "val",
    [0.0, 0.5, 1.0],
)
class TestParametrized:
    def test_plugin_from_instance(self, val: float) -> None:

        assert plugin_from_instance(val) is DoublePlugin

    def test_value_to_json(self, val: float) -> None:

        assert DoublePlugin.value_to_json(val) == json.dumps(val)

    def test_get_value(self, val: float) -> None:

        scene = Scene("s1", "s1")
        obj_id = "TestId"
        scene.objects.append(SceneObject(obj_id, "test_name", TestObject.__name__))
        project = Project("p1", "p1", "s1")
        ap1 = ActionPoint("ap1", "ap1", Position())
        project.action_points.append(ap1)

        invalid_param_name = "invalid_param"
        action_id = "ac1"

        ap1.actions.append(
            Action(
                action_id,
                action_id,
                f"{obj_id}/{TestObject.action.__name__}",
                [
                    ActionParameter(param_name, DoublePlugin.type_name(), DoublePlugin.value_to_json(val)),
                    ActionParameter(invalid_param_name, DoublePlugin.type_name(), json.dumps("non_sense")),
                ],
            )
        )

        cscene = CachedScene(scene)
        cproject = CachedProject(project)

        with pytest.raises(Arcor2Exception):
            DoublePlugin.parameter_value({}, cscene, cproject, action_id, "non_sense")

        with pytest.raises(Arcor2Exception):
            DoublePlugin.parameter_value({}, cscene, cproject, "non_sense", param_name)

        with pytest.raises(ParameterPluginException):
            DoublePlugin.parameter_value({}, cscene, cproject, action_id, invalid_param_name)

        value = DoublePlugin.parameter_value({}, cscene, cproject, action_id, param_name)
        exe_value = DoublePlugin.parameter_execution_value({}, cscene, cproject, action_id, param_name)

        assert value == val
        assert value == exe_value
