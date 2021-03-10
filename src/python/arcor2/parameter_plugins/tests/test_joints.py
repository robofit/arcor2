import inspect
import json
from typing import Dict, Type

import pytest

from arcor2.cached import CachedProject, CachedScene
from arcor2.data.common import (
    Action,
    ActionParameter,
    ActionPoint,
    Joint,
    Position,
    Project,
    ProjectRobotJoints,
    Scene,
    SceneObject,
)
from arcor2.exceptions import Arcor2Exception
from arcor2.object_types.abstract import Generic
from arcor2.parameter_plugins import ParameterPluginException
from arcor2.parameter_plugins.joints import JointsPlugin
from arcor2.parameter_plugins.utils import plugin_from_instance, plugin_from_type


class TestObject(Generic):
    def action(self, arbitrary_type_param: str, joints_param: ProjectRobotJoints, some_other_param: int) -> None:
        pass


param_name = "joints_param"
type_defs: Dict[str, Type[Generic]] = {TestObject.__name__: TestObject}


def test_abstract() -> None:
    assert not inspect.isabstract(JointsPlugin)


def test_plugin_from_type() -> None:

    assert plugin_from_type(ProjectRobotJoints) is JointsPlugin


def test_plugin_from_instance() -> None:

    assert plugin_from_instance(ProjectRobotJoints("name", "robot_id", [Joint("name", 0.333)])) is JointsPlugin


def test_value_to_json() -> None:

    prj = ProjectRobotJoints("name", "robot_id", [Joint("name", 0.333)])
    assert JointsPlugin.value_to_json(prj) == prj.to_json()


def test_get_value() -> None:

    scene = Scene("s1", "s1")
    obj = SceneObject("test_name", TestObject.__name__)
    prj = ProjectRobotJoints("name", obj.id, [Joint("name", 0.333)])
    scene.objects.append(obj)
    project = Project("p1", "s1")
    ap1 = ActionPoint("ap1", Position(1, 0, 0))
    ap1.robot_joints.append(prj)
    project.action_points.append(ap1)

    invalid_param_name = "invalid_param"

    act = Action(
        "ac1",
        f"{obj.id}/{TestObject.action.__name__}",
        parameters=[
            ActionParameter(param_name, JointsPlugin.type_name(), json.dumps(prj.id)),
            ActionParameter(invalid_param_name, JointsPlugin.type_name(), json.dumps("non_sense")),
        ],
    )

    ap1.actions.append(act)

    cscene = CachedScene(scene)
    cproject = CachedProject(project)

    with pytest.raises(Arcor2Exception):
        JointsPlugin.parameter_value(type_defs, cscene, cproject, act.id, "non_sense")

    with pytest.raises(Arcor2Exception):
        JointsPlugin.parameter_value(type_defs, cscene, cproject, "non_sense", param_name)

    with pytest.raises(ParameterPluginException):
        JointsPlugin.parameter_value(type_defs, cscene, cproject, act.id, invalid_param_name)

    value = JointsPlugin.parameter_value(type_defs, cscene, cproject, act.id, param_name)
    exe_value = JointsPlugin.parameter_execution_value(type_defs, cscene, cproject, act.id, param_name)

    assert value == value
    assert value == exe_value
