import inspect
import json
from typing import Dict, Type

import pytest  # type: ignore

from arcor2.cached import CachedProject, CachedScene
from arcor2.data.common import Action, ActionParameter, ActionPoint, Position, Project, Scene, SceneObject, StrEnum
from arcor2.data.object_type import ParameterMeta
from arcor2.exceptions import Arcor2Exception
from arcor2.object_types.abstract import Generic
from arcor2.parameter_plugins import ParameterPluginException
from arcor2.parameter_plugins.integer_enum import IntegerEnumExtra
from arcor2.parameter_plugins.string_enum import StringEnumPlugin
from arcor2.parameter_plugins.utils import plugin_from_instance, plugin_from_type
from arcor2.source.utils import find_function, parse_def


class TestEnum(StrEnum):

    FIRST = "first"
    SECOND = "second"


class TestObject(Generic):
    def action(self, arbitrary_type_param: str, enum_param: TestEnum, some_other_param: int) -> None:
        pass


param_name = "enum_param"
type_defs: Dict[str, Type[Generic]] = {TestObject.__name__: TestObject}


def test_abstract() -> None:
    assert not inspect.isabstract(StringEnumPlugin)


def test_plugin_from_type() -> None:

    assert plugin_from_type(TestEnum) is StringEnumPlugin


def test_meta() -> None:

    meta = ParameterMeta(param_name, StringEnumPlugin.type_name())
    StringEnumPlugin.meta(meta, TestObject.action, find_function(TestObject.action.__name__, parse_def(TestObject)))
    assert meta.extra

    extra = IntegerEnumExtra.from_json(meta.extra)

    assert extra.allowed_values == TestEnum.set()


@pytest.mark.parametrize(
    "val",
    [TestEnum.FIRST, TestEnum.SECOND],
)
class TestParametrized:
    def test_plugin_from_instance(self, val: TestEnum) -> None:

        assert plugin_from_instance(val) is StringEnumPlugin

    def test_value_to_json(self, val: TestEnum) -> None:

        assert StringEnumPlugin.value_to_json(val) == json.dumps(val)

    def test_get_value(self, val: TestEnum) -> None:

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
                    ActionParameter(param_name, StringEnumPlugin.type_name(), StringEnumPlugin.value_to_json(val)),
                    ActionParameter(invalid_param_name, StringEnumPlugin.type_name(), json.dumps("non_sense")),
                ],
            )
        )

        cscene = CachedScene(scene)
        cproject = CachedProject(project)

        with pytest.raises(Arcor2Exception):
            StringEnumPlugin.parameter_value(type_defs, cscene, cproject, action_id, "non_sense")

        with pytest.raises(Arcor2Exception):
            StringEnumPlugin.parameter_value(type_defs, cscene, cproject, "non_sense", param_name)

        with pytest.raises(ParameterPluginException):
            StringEnumPlugin.parameter_value(type_defs, cscene, cproject, action_id, invalid_param_name)

        value = StringEnumPlugin.parameter_value(type_defs, cscene, cproject, action_id, param_name)
        exe_value = StringEnumPlugin.parameter_execution_value(type_defs, cscene, cproject, action_id, param_name)

        assert value == val
        assert value == exe_value
