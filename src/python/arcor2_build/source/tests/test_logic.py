import json
from typing import List, Optional

import pytest

from arcor2.cached import CachedProject, CachedScene
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
from arcor2.object_types.abstract import Generic
from arcor2.source import SourceException
from arcor2.source.utils import parse
from arcor2_build.source.logic import program_src

TAB = 4


class Test(Generic):
    def test(self, *, an: Optional[str] = None):
        pass


def subs_index(spl: List[str], subs: str) -> int:
    """Returns index of the list's first element that contains given substring.

    :param spl:
    :param subs:
    :return:
    """

    for idx, sp in enumerate(spl):
        if subs in sp:
            return idx

    raise ValueError(f"Substring '{subs}' not found.")


def cntsp(a: str) -> int:
    """Counts spaces at the beginning of the string.

    :param a:
    :return:
    """

    return len(a) - len(a.lstrip(" "))


@pytest.mark.repeat(10)
def test_blind_branch() -> None:

    scene = Scene("s1", "s1")
    scene.objects.append(SceneObject("TestId", "test_name", Test.__name__))
    project = Project("p1", "p1", "s1")
    ap1 = ActionPoint("ap1", "ap1", Position())
    project.action_points.append(ap1)

    ap1.actions.append(Action("ac1", "ac1", "TestId/test", flows=[Flow(outputs=["bool_res"])]))

    ap1.actions.append(Action("ac2", "ac2", "TestId/test", flows=[Flow()]))
    ap1.actions.append(Action("ac3", "ac3", "TestId/test", flows=[Flow()]))
    ap1.actions.append(Action("ac4", "ac4", "TestId/test", flows=[Flow()]))

    project.logic.append(LogicItem("l1", LogicItem.START, "ac1"))

    project.logic.append(LogicItem("l2", "ac1", "ac2", ProjectLogicIf("ac1/default/0", json.dumps(True))))
    project.logic.append(LogicItem("l3", "ac1", "ac3", ProjectLogicIf("ac1/default/0", json.dumps(False))))

    project.logic.append(LogicItem("l4", "ac2", "ac4"))
    project.logic.append(LogicItem("l6", "ac4", LogicItem.END))

    with pytest.raises(SourceException, match="Action ac3 has no outputs."):
        program_src({Test.__name__: Test}, CachedProject(project), CachedScene(scene))


@pytest.mark.repeat(10)
def test_branched_output() -> None:

    scene = Scene("s1", "s1")
    scene.objects.append(SceneObject("TestId", "test_name", "Test"))
    project = Project("p1", "p1", "s1")
    ap1 = ActionPoint("ap1", "ap1", Position())
    project.action_points.append(ap1)

    ap1.actions.append(Action("ac1", "ac1", "TestId/test", flows=[Flow(outputs=["bool_res"])]))

    ap1.actions.append(Action("ac2", "ac2", "TestId/test", flows=[Flow()]))
    ap1.actions.append(Action("ac3", "ac3", "TestId/test", flows=[Flow()]))
    ap1.actions.append(Action("ac4", "ac4", "TestId/test", flows=[Flow()]))

    project.logic.append(LogicItem("l1", LogicItem.START, "ac1"))

    project.logic.append(LogicItem("l2", "ac1", "ac2", ProjectLogicIf("ac1/default/0", json.dumps(True))))
    project.logic.append(LogicItem("l3", "ac1", "ac3", ProjectLogicIf("ac1/default/0", json.dumps(False))))

    project.logic.append(LogicItem("l4", "ac2", "ac4"))
    project.logic.append(LogicItem("l5", "ac3", "ac4"))
    project.logic.append(LogicItem("l6", "ac4", LogicItem.END))

    src = program_src({Test.__name__: Test}, CachedProject(project), CachedScene(scene))
    parse(src)

    """
    bool_res = test_name.test(res.ac1)
    if (bool_res == False):
        test_name.test(res.ac3)
    elif (bool_res == True):
        test_name.test(res.ac2)
    test_name.test(res.ac4)
    """

    spl = src.splitlines()

    ac1_idx = subs_index(spl, "bool_res = test_name.test(an='ac1')")

    if_bool_res_false_idx = subs_index(spl, "if (bool_res == False):")
    assert if_bool_res_false_idx > ac1_idx
    assert cntsp(spl[if_bool_res_false_idx]) == cntsp(spl[ac1_idx])
    assert "test_name.test(an='ac3')" in spl[if_bool_res_false_idx + 1]
    assert cntsp(spl[if_bool_res_false_idx]) == cntsp(spl[if_bool_res_false_idx + 1]) - TAB

    if_bool_res_true_idx = subs_index(spl, "if (bool_res == True):")
    assert if_bool_res_true_idx > ac1_idx
    assert cntsp(spl[if_bool_res_true_idx]) == cntsp(spl[ac1_idx])
    assert "test_name.test(an='ac2')" in spl[if_bool_res_true_idx + 1]
    assert cntsp(spl[if_bool_res_true_idx]) == cntsp(spl[if_bool_res_true_idx + 1]) - TAB

    ac4_idx = subs_index(spl, "test_name.test(an='ac4')")
    assert ac4_idx > if_bool_res_false_idx
    assert ac4_idx > if_bool_res_true_idx
    assert cntsp(spl[ac4_idx]) == cntsp(spl[ac1_idx])


@pytest.mark.repeat(10)
def test_branched_output_2() -> None:

    scene = Scene("s1", "s1")
    scene.objects.append(SceneObject("TestId", "test_name", Test.__name__))
    project = Project("p1", "p1", "s1")
    ap1 = ActionPoint("ap1", "ap1", Position())
    project.action_points.append(ap1)

    ap1.actions.append(Action("ac1", "ac1", "TestId/test", flows=[Flow(outputs=["bool_res"])]))

    ap1.actions.append(Action("ac2", "ac2", "TestId/test", flows=[Flow()]))
    ap1.actions.append(Action("ac3", "ac3", "TestId/test", flows=[Flow()]))

    ap1.actions.append(Action("ac4", "ac4", "TestId/test", flows=[Flow(outputs=["bool2_res"])]))

    ap1.actions.append(Action("ac5", "ac5", "TestId/test", flows=[Flow()]))
    ap1.actions.append(Action("ac6", "ac6", "TestId/test", flows=[Flow()]))

    project.logic.append(LogicItem("l1", LogicItem.START, "ac1"))

    project.logic.append(LogicItem("l2", "ac1", "ac2", ProjectLogicIf("ac1/default/0", json.dumps(True))))
    project.logic.append(LogicItem("l3", "ac1", "ac4", ProjectLogicIf("ac1/default/0", json.dumps(False))))

    project.logic.append(LogicItem("l4", "ac2", "ac3"))
    project.logic.append(LogicItem("l5", "ac3", "ac6"))

    project.logic.append(LogicItem("l6", "ac4", "ac5", ProjectLogicIf("ac4/default/0", json.dumps(True))))
    project.logic.append(LogicItem("l7", "ac5", "ac6"))
    project.logic.append(LogicItem("l8", "ac6", LogicItem.END))

    project.logic.append(LogicItem("l9", "ac4", LogicItem.END, ProjectLogicIf("ac4/default/0", json.dumps(False))))

    src = program_src({Test.__name__: Test}, CachedProject(project), CachedScene(scene))
    parse(src)

    """
    bool_res = test_name.test(res.ac1)
    if (bool_res == False):
        bool2_res = test_name.test(res.ac4)
        if (bool2_res == False):
            continue
        elif (bool2_res == True):
            test_name.test(res.ac5)
    elif (bool_res == True):
        test_name.test(res.ac2)
        test_name.test(res.ac3)
    test_name.test(res.ac6)
    """

    spl = src.splitlines()

    # it has to be robust against changed order of blocks
    ac1_idx = subs_index(spl, "bool_res = test_name.test(an='ac1')")

    if_bool_res_false_idx = subs_index(spl, "if (bool_res == False):")
    assert if_bool_res_false_idx > ac1_idx
    assert cntsp(spl[ac1_idx]) == cntsp(spl[if_bool_res_false_idx])

    bool2_res_idx = subs_index(spl, "bool2_res = test_name.test(an='ac4')")
    assert bool2_res_idx > if_bool_res_false_idx
    assert cntsp(spl[if_bool_res_false_idx]) == cntsp(spl[bool2_res_idx]) - TAB

    if_bool_2_res_false_idx = subs_index(spl, "if (bool2_res == False):")
    assert cntsp(spl[if_bool_2_res_false_idx]) == cntsp(spl[bool2_res_idx])
    assert if_bool_2_res_false_idx > bool2_res_idx
    assert "continue" in spl[if_bool_2_res_false_idx + 1]
    assert cntsp(spl[bool2_res_idx]) == cntsp(spl[if_bool_2_res_false_idx + 1]) - TAB

    if_bool_2_res_true_idx = subs_index(spl, "if (bool2_res == True):")
    assert if_bool_2_res_true_idx > bool2_res_idx
    assert "test_name.test(an='ac5')" in spl[if_bool_2_res_true_idx + 1]
    assert cntsp(spl[if_bool_2_res_true_idx]) == cntsp(spl[if_bool_2_res_true_idx + 1]) - TAB

    if_bool_res_true_idx = subs_index(spl, "if (bool_res == True):")
    assert if_bool_res_true_idx > ac1_idx
    assert cntsp(spl[ac1_idx]) == cntsp(spl[if_bool_res_true_idx])

    assert "test_name.test(an='ac2')" in spl[if_bool_res_true_idx + 1]
    assert cntsp(spl[if_bool_res_true_idx]) == cntsp(spl[if_bool_res_true_idx + 1]) - TAB

    assert "test_name.test(an='ac3')" in spl[if_bool_res_true_idx + 2]
    assert cntsp(spl[if_bool_res_true_idx]) == cntsp(spl[if_bool_res_true_idx + 2]) - TAB

    ac6_idx = subs_index(spl, "test_name.test(an='ac6')")
    assert cntsp(spl[ac1_idx]) == cntsp(spl[ac6_idx])
    assert ac6_idx > if_bool_2_res_false_idx
    assert ac6_idx > if_bool_2_res_true_idx
