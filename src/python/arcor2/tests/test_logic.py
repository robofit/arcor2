import json

import pytest

from arcor2.cached import UpdateableCachedProject
from arcor2.data.common import (
    Action,
    ActionPoint,
    Flow,
    LogicItem,
    Position,
    Project,
    ProjectLogicIf,
    Scene,
    SceneObject,
)
from arcor2.exceptions import Arcor2Exception
from arcor2.logic import check_for_loops

obj = SceneObject("test_name", "Test")
ac1 = Action("ac1", f"{obj.id}/test", flows=[Flow(outputs=["bool_res"])])
ac2 = Action("ac2", f"{obj.id}/test", flows=[Flow()])
ac3 = Action("ac3", f"{obj.id}/test", flows=[Flow()])
ac4 = Action("ac4", f"{obj.id}/test", flows=[Flow()])


@pytest.fixture
def scene() -> Scene:
    scene = Scene("s1", "s1")
    scene.objects.append(obj)
    return scene


@pytest.fixture
def project() -> UpdateableCachedProject:
    project = Project("p1", "s1")
    ap1 = ActionPoint("ap1", Position())
    project.action_points.append(ap1)

    ap1.actions.append(ac1)
    ap1.actions.append(ac2)
    ap1.actions.append(ac3)
    ap1.actions.append(ac4)
    return UpdateableCachedProject(project)


def test_project_wo_loop(scene: Scene, project: UpdateableCachedProject) -> None:
    project.upsert_logic_item(LogicItem(LogicItem.START, ac1.id))
    project.upsert_logic_item(LogicItem(ac1.id, ac2.id))
    project.upsert_logic_item(LogicItem(ac2.id, ac3.id))
    project.upsert_logic_item(LogicItem(ac3.id, ac4.id))
    project.upsert_logic_item(LogicItem(ac4.id, LogicItem.END))

    check_for_loops(project)


def test_project_wo_loop_branched_logic(scene: Scene, project: UpdateableCachedProject) -> None:
    project.upsert_logic_item(LogicItem(LogicItem.START, ac1.id))
    project.upsert_logic_item(LogicItem(ac1.id, ac2.id, ProjectLogicIf(f"{ac1.id}/default/0", json.dumps(True))))
    project.upsert_logic_item(LogicItem(ac1.id, ac3.id, ProjectLogicIf(f"{ac1.id}/default/0", json.dumps(False))))
    project.upsert_logic_item(LogicItem(ac2.id, ac4.id))
    project.upsert_logic_item(LogicItem(ac3.id, ac4.id))
    project.upsert_logic_item(LogicItem(ac4.id, LogicItem.END))

    check_for_loops(project)


def test_project_with_loop(scene: Scene, project: UpdateableCachedProject) -> None:
    project.upsert_logic_item(LogicItem(LogicItem.START, ac1.id))
    project.upsert_logic_item(LogicItem(ac1.id, ac2.id))
    project.upsert_logic_item(LogicItem(ac2.id, ac3.id))
    project.upsert_logic_item(LogicItem(ac3.id, ac4.id))
    project.upsert_logic_item(LogicItem(ac4.id, ac1.id))

    with pytest.raises(Arcor2Exception):
        check_for_loops(project)


def test_project_unfinished_logic_wo_loop(scene: Scene, project: UpdateableCachedProject) -> None:
    project.upsert_logic_item(LogicItem(ac1.id, ac2.id))
    check_for_loops(project, ac1.id)


def test_project_unfinished_logic_with_loop(scene: Scene, project: UpdateableCachedProject) -> None:
    project.upsert_logic_item(LogicItem(ac1.id, ac2.id))
    project.upsert_logic_item(LogicItem(ac2.id, ac1.id))

    with pytest.raises(Arcor2Exception):
        check_for_loops(project, ac1.id)
