import pytest  # type: ignore

from arcor2.cached import UpdateableCachedProject
from arcor2.data.common import Action, ActionPoint, Flow, LogicItem, Position, Project, Scene
from arcor2.exceptions import Arcor2Exception
from arcor2.logic import check_for_loops


@pytest.fixture()
def scene() -> Scene:

    return Scene("s1", "s1")


@pytest.fixture()
def project() -> UpdateableCachedProject:

    project = Project("p1", "p1", "s1")
    ap1 = ActionPoint("ap1", "ap1", Position())
    project.action_points.append(ap1)

    ap1.actions.append(Action("ac1", "ac1", "Test/test", flows=[Flow()]))
    ap1.actions.append(Action("ac2", "ac2", "Test/test", flows=[Flow()]))
    return UpdateableCachedProject(project)


def test_project_wo_loop(scene: Scene, project: UpdateableCachedProject) -> None:

    project.upsert_logic_item(LogicItem("l1", LogicItem.START, "ac1"))
    project.upsert_logic_item(LogicItem("l2", "ac1", "ac2"))
    project.upsert_logic_item(LogicItem("l3", "ac2", LogicItem.END))

    check_for_loops(project)


def test_project_with_loop(scene: Scene, project: UpdateableCachedProject) -> None:

    project.upsert_logic_item(LogicItem("l1", LogicItem.START, "ac1"))
    project.upsert_logic_item(LogicItem("l2", "ac1", "ac2"))
    project.upsert_logic_item(LogicItem("l3", "ac2", LogicItem.END))
    project.upsert_logic_item(LogicItem("l4", "ac2", "ac1"))

    with pytest.raises(Arcor2Exception):
        check_for_loops(project)


def test_project_with_loop_2(scene: Scene, project: UpdateableCachedProject) -> None:

    project.upsert_logic_item(LogicItem("l1", "ac1", "ac2"))
    project.upsert_logic_item(LogicItem("l2", "ac2", "ac1"))

    with pytest.raises(Arcor2Exception):
        check_for_loops(project)


def test_project_unfinished_logic_wo_loop(scene: Scene, project: UpdateableCachedProject) -> None:

    project.upsert_logic_item(LogicItem("l1", "ac1", "ac2"))
    check_for_loops(project, "ac1")


def test_project_unfinished_logic_with_loop(scene: Scene, project: UpdateableCachedProject) -> None:

    project.upsert_logic_item(LogicItem("l1", "ac1", "ac2"))
    project.upsert_logic_item(LogicItem("l2", "ac2", "ac1"))

    with pytest.raises(Arcor2Exception):
        check_for_loops(project, "ac1")
