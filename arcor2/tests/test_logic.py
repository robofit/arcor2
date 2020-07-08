import pytest  # type: ignore

from arcor2.data.common import Action, Flow, LogicItem, Position, Project, ProjectActionPoint, Scene
from arcor2.exceptions import Arcor2Exception
from arcor2.logic import check_for_loops


@pytest.fixture()
def scene() -> Scene:

    return Scene("s1", "s1")


@pytest.fixture()
def project() -> Project:

    project = Project("p1", "p1", "s1")
    ap1 = ProjectActionPoint("ap1", "ap1", Position())
    project.action_points.append(ap1)

    ap1.actions.append(Action("ac1", "ac1", "Test/test", flows=[Flow()]))
    ap1.actions.append(Action("ac2", "ac2", "Test/test", flows=[Flow()]))
    return project


def test_project_wo_loop(scene: Scene, project: Project):

    project.logic.append(LogicItem("l1", LogicItem.START, "ac1"))
    project.logic.append(LogicItem("l2", "ac1", "ac2"))
    project.logic.append(LogicItem("l3", "ac2", LogicItem.END))

    check_for_loops(project)


def test_project_with_loop(scene: Scene, project: Project):

    project.logic.append(LogicItem("l1", LogicItem.START, "ac1"))
    project.logic.append(LogicItem("l2", "ac1", "ac2"))
    project.logic.append(LogicItem("l3", "ac2", LogicItem.END))
    project.logic.append(LogicItem("l4", "ac2", "ac1"))

    with pytest.raises(Arcor2Exception):
        check_for_loops(project)


def test_project_with_loop_2(scene: Scene, project: Project):

    project.logic.append(LogicItem("l1", "ac1", "ac2"))
    project.logic.append(LogicItem("l2", "ac2", "ac1"))

    with pytest.raises(Arcor2Exception):
        check_for_loops(project)


def test_project_unfinished_logic_wo_loop(scene: Scene, project: Project):

    project.logic.append(LogicItem("l1", "ac1", "ac2"))
    check_for_loops(project, "ac1")


def test_project_unfinished_logic_with_loop(scene: Scene, project: Project):

    project.logic.append(LogicItem("l1", "ac1", "ac2"))
    project.logic.append(LogicItem("l2", "ac2", "ac1"))

    with pytest.raises(Arcor2Exception):
        check_for_loops(project, "ac1")
