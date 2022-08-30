import inspect
import json

import pytest

from arcor2.cached import CachedProject, CachedScene
from arcor2.data.common import Action, ActionParameter, ActionPoint, Position, Project, Scene, SceneObject
from arcor2.exceptions import Arcor2Exception
from arcor2.object_types.abstract import Generic
from arcor2.parameter_plugins import ParameterPluginException
from arcor2.parameter_plugins.position import PositionPlugin
from arcor2.parameter_plugins.utils import plugin_from_instance, plugin_from_type


class TestObject(Generic):
    def action(self, arbitrary_type_param: str, position_param: Position, some_other_param: int) -> None:
        pass


param_name = "position_param"
type_defs: dict[str, type[Generic]] = {TestObject.__name__: TestObject}


def test_abstract() -> None:
    assert not inspect.isabstract(PositionPlugin)


def test_plugin_from_type() -> None:

    assert plugin_from_type(Position) is PositionPlugin


def test_plugin_from_instance() -> None:

    assert plugin_from_instance(Position()) is PositionPlugin


def test_value_to_json() -> None:

    p = Position()
    assert PositionPlugin.value_to_json(p) == p.to_json()


def test_get_value() -> None:

    scene = Scene("s1")
    obj = SceneObject("test_name", TestObject.__name__)
    scene.objects.append(obj)
    project = Project("p1", "s1")
    ap1 = ActionPoint("ap1", Position(1, 0, 0))
    project.action_points.append(ap1)
    ap2 = ActionPoint("ap2", Position(1, 2, 3), parent=ap1.id)
    project.action_points.append(ap2)

    invalid_param_name = "invalid_param"

    ac1 = Action(
        "ac1",
        f"{obj.id}/{TestObject.action.__name__}",
        parameters=[
            ActionParameter(param_name, PositionPlugin.type_name(), json.dumps(ap2.id)),
            ActionParameter(invalid_param_name, PositionPlugin.type_name(), json.dumps("non_sense")),
        ],
    )

    ap1.actions.append(ac1)

    cscene = CachedScene(scene)
    cproject = CachedProject(project)

    with pytest.raises(Arcor2Exception):
        PositionPlugin.parameter_value(type_defs, cscene, cproject, ac1.id, "non_sense")

    with pytest.raises(Arcor2Exception):
        PositionPlugin.parameter_value(type_defs, cscene, cproject, "non_sense", param_name)

    with pytest.raises(ParameterPluginException):
        PositionPlugin.parameter_value(type_defs, cscene, cproject, ac1.id, invalid_param_name)

    value = PositionPlugin.parameter_value(type_defs, cscene, cproject, ac1.id, param_name)
    exe_value = PositionPlugin.parameter_execution_value(type_defs, cscene, cproject, ac1.id, param_name)

    assert value == ap2.position
    assert value != exe_value
