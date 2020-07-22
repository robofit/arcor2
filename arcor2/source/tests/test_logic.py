from arcor2.cached import CachedProject, CachedScene
from arcor2.data.common import Action, Flow, LogicItem, Position, Project, ProjectActionPoint, Scene
from arcor2.source.logic import program_src


def test_program_src() -> None:

    scene = Scene("s1", "s1")
    project = Project("p1", "p1", "s1")
    ap1 = ProjectActionPoint("ap1", "ap1", Position())
    project.action_points.append(ap1)

    ap1.actions.append(Action("ac1", "ac1", "Test/test", flows=[Flow()]))
    ap1.actions.append(Action("ac2", "ac2", "Test/test", flows=[Flow()]))

    project.logic.append(LogicItem("l1", LogicItem.START, "ac1"))
    project.logic.append(LogicItem("l2", "ac1", "ac2"))
    project.logic.append(LogicItem("l3", "ac2", LogicItem.END))

    src = program_src(CachedProject(project), CachedScene(scene), set())

    assert "test.test(res.ac1)" in src
    assert "test.test(res.ac2)" in src
