import inspect
import json
from typing import Dict, Type

import pytest  # type: ignore

from arcor2.cached import CachedProject, CachedScene
from arcor2.data.common import (
    Action,
    ActionParameter,
    ActionPoint,
    NamedOrientation,
    Orientation,
    Pose,
    Position,
    Project,
    Scene,
    SceneObject,
)
from arcor2.exceptions import Arcor2Exception
from arcor2.object_types.abstract import Generic
from arcor2.parameter_plugins import ParameterPluginException
from arcor2.parameter_plugins.pose import PosePlugin
from arcor2.parameter_plugins.utils import plugin_from_instance, plugin_from_type


class TestObject(Generic):
    def action(self, arbitrary_type_param: str, pose_param: Pose, some_other_param: int) -> None:
        pass


param_name = "pose_param"
type_defs: Dict[str, Type[Generic]] = {TestObject.__name__: TestObject}


def test_abstract() -> None:
    assert not inspect.isabstract(PosePlugin)


def test_plugin_from_type() -> None:

    assert plugin_from_type(Pose) is PosePlugin


def test_plugin_from_instance() -> None:

    assert plugin_from_instance(Pose()) is PosePlugin


def test_value_to_json() -> None:

    p = Pose()
    assert PosePlugin.value_to_json(p) == p.to_json()


def test_get_value() -> None:

    p = Pose(Position(1, 2, 3), Orientation(1, 0, 0, 0))

    scene = Scene("s1", "s1")
    obj_id = "TestId"
    scene.objects.append(SceneObject(obj_id, "test_name", TestObject.__name__))
    project = Project("p1", "p1", "s1")
    ap1 = ActionPoint("ap1", "ap1", Position(1, 0, 0))
    project.action_points.append(ap1)
    ap2 = ActionPoint("ap2", "ap2", Position(), parent="ap1")
    project.action_points.append(ap2)

    ori_id = "or1"
    ap2.orientations.append(NamedOrientation(ori_id, ori_id, p.orientation))

    invalid_param_name = "invalid_param"
    action_id = "ac1"

    ap1.actions.append(
        Action(
            action_id,
            action_id,
            f"{obj_id}/{TestObject.action.__name__}",
            [
                ActionParameter(param_name, PosePlugin.type_name(), json.dumps(ori_id)),
                ActionParameter(invalid_param_name, PosePlugin.type_name(), json.dumps("non_sense")),
            ],
        )
    )

    cscene = CachedScene(scene)
    cproject = CachedProject(project)

    with pytest.raises(Arcor2Exception):
        PosePlugin.parameter_value(type_defs, cscene, cproject, action_id, "non_sense")

    with pytest.raises(Arcor2Exception):
        PosePlugin.parameter_value(type_defs, cscene, cproject, "non_sense", param_name)

    with pytest.raises(ParameterPluginException):
        PosePlugin.parameter_value(type_defs, cscene, cproject, action_id, invalid_param_name)

    value = PosePlugin.parameter_value(type_defs, cscene, cproject, action_id, param_name)
    exe_value = PosePlugin.parameter_execution_value(type_defs, cscene, cproject, action_id, param_name)

    assert value == value
    assert value != exe_value
