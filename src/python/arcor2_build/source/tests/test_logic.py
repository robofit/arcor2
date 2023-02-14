import json
import pytest

from arcor2.cached import CachedProject, CachedScene
from arcor2.data.common import (
    Action,
    ActionParameter,
    ActionPoint,
    Flow,
    LogicItem,
    Position,
    Project,
    ProjectLogicIf,
    ProjectParameter,
    Scene,
    SceneObject,
)
from arcor2.object_types.abstract import Generic
from arcor2.source import SourceException
from arcor2.source.utils import parse
from arcor2_build.source.logic import program_src
from arcor2_build.source.python_to_json import get_pro_sce_scr, python_to_json

TAB = 4
class Test(Generic):

    INT = 1234

    def get_int(self, *, an: None | str = None) -> int:
        return self.INT

    def test(self, *, an: None | str = None) -> bool:
        return True

    def test_par(self, param: int, *, an: None | str = None) -> None:
        pass


def subs_index(spl: list[str], subs: str) -> int:
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

###################################

def find_action_from_id(id: str, project: Project):

    for k in range(len(project.action_points)):
        for i in project.action_points[k].actions:
            if id == i.id:
                return i
    raise "Action whit id:"+id+" in project:"+project.name+"does not exisit"

def find_action_from_name(name: str, project: Project):

    for k in range(len(project.action_points)):
        for i in project.action_points[k].actions:
            if name == i.name:
                return i
    raise "Action whit name:"+name+" in project:"+project.name+"does not exisit"

def find_logic_item(start: str, end: str, project: Project):

    for i in project.logic:
        if start == i.start and end == i.end:
                return i
    raise "Logic item whit START: "+start+" and END: "+end+" in project:"+project.name+"does not exisist"

def test_python_to_json() -> None:

    test_files = {"test_const","test_prev_result","test_simple_if","test_if"}
    original_project= None 
    scene = None
    src = None
    for i in test_files:

        original_project, scene, src = get_pro_sce_scr(i)
        modified_project = python_to_json(i)

        """modified_project = Project("modified_project", "s1")
        modified_project = between_step(original_project, scene, src)"""

        o_p = CachedProject(original_project)
        m_p = CachedProject(modified_project)

        assert (len(o_p.actions)) == (len(m_p.actions))
        assert (len(o_p.logic)) == (len(m_p.logic))

        start_modified_action = None
        end_modif_action = None
        start_orig_action = None
        start_orig_action_id = None
        end_orig_action = None
        end_orig_action_id = None
        orig_logic_item = None
        for modif_logic_item in modified_project.logic:

            if modif_logic_item.start != LogicItem.START:
                start_modified_action = find_action_from_id(modif_logic_item.start, modified_project)
                start_orig_action = find_action_from_name(start_modified_action.name, original_project)
                assert start_modified_action.name == start_orig_action.name
                assert start_modified_action.type == start_orig_action.type
                assert start_modified_action.flows == start_orig_action.flows
                #assert start_modified_action.parameters == start_orig_action.parameters
                start_orig_action_id = start_orig_action.id
            else:
                start_orig_action_id = LogicItem.START

            if modif_logic_item.end != LogicItem.END:
                end_modif_action = find_action_from_id(modif_logic_item.end, modified_project)
                end_orig_action = find_action_from_name(end_modif_action.name, original_project)
                assert end_modif_action.name == end_orig_action.name
                assert end_modif_action.type == end_orig_action.type
                assert end_modif_action.flows == end_orig_action.flows
                #assert end_modif_action.parameters == end_orig_action.parameters
                end_orig_action_id = end_orig_action.id
            else:
                end_orig_action_id = LogicItem.END

            orig_logic_item = find_logic_item(start_orig_action_id,end_orig_action_id, original_project)
            if modif_logic_item.condition == None:
                assert orig_logic_item.condition == None
            else:
                assert modif_logic_item.condition.value == orig_logic_item.condition.value
                tmp1 = modif_logic_item.condition.what
                tmp2 = orig_logic_item.condition.what
                try:
                    tmp1 = tmp1.removesuffix("/default/0")
                except:
                    raise "what in condition is not variable"
                tmp2 = tmp2.removesuffix("/default/0")
                
                modif_con = find_action_from_id(tmp1, modified_project)
                orig_con = find_action_from_id(tmp2, original_project)
                assert modif_con.name == orig_con.name
                assert modif_con.type == orig_con.type
                assert modif_con.flows == orig_con.flows

############################

def test_prev_result() -> None:

    scene = Scene("s1")
    obj = SceneObject("test_name", Test.__name__)
    scene.objects.append(obj)
    project = Project("p1", "s1")
    ap1 = ActionPoint("ap1", Position())
    project.action_points.append(ap1)

    ac1 = Action("ac1", f"{obj.id}/{Test.get_int.__name__}", flows=[Flow(outputs=["res"])])
    ap1.actions.append(ac1)

    ac2 = Action(
        "ac2",
        f"{obj.id}/{Test.test_par.__name__}",
        flows=[Flow()],
        parameters=[ActionParameter("param", ActionParameter.TypeEnum.LINK, json.dumps(f"{ac1.id}/default/0"))],
    )
    ap1.actions.append(ac2)

    project.logic.append(LogicItem(LogicItem.START, ac1.id))
    project.logic.append(LogicItem(ac1.id, ac2.id))
    project.logic.append(LogicItem(ac2.id, LogicItem.END))

    src = program_src({Test.__name__: Test}, CachedProject(project), CachedScene(scene))

    assert f"res = test_name.{Test.get_int.__name__}(an='{ac1.name}')" in src
    assert f"test_name.{Test.test_par.__name__}(res, an='{ac2.name}')" in src

    # test wrong order of logic
    project.logic.clear()

    project.logic.append(LogicItem(LogicItem.START, ac2.id))
    project.logic.append(LogicItem(ac2.id, ac1.id))
    project.logic.append(LogicItem(ac1.id, LogicItem.END))

    with pytest.raises(SourceException):
        program_src({Test.__name__: Test}, CachedProject(project), CachedScene(scene))

def test_constant() -> None:

    scene = Scene("s1")
    obj = SceneObject("test_name", Test.__name__)
    scene.objects.append(obj)
    project = Project("p1", "s1")
    ap1 = ActionPoint("ap1", Position())
    project.action_points.append(ap1)

    const_value = 1234
    const = ProjectParameter("int_const", "integer", json.dumps(const_value))
    project.parameters.append(const)

    ac1 = Action(
        "ac1",
        f"{obj.id}/test_par",
        flows=[Flow()],
        parameters=[ActionParameter("param", ActionParameter.TypeEnum.PROJECT_PARAMETER, json.dumps(const.id))],
    )

    ap1.actions.append(ac1)

    project.logic.append(LogicItem(LogicItem.START, ac1.id))
    project.logic.append(LogicItem(ac1.id, LogicItem.END))

    src = program_src({Test.__name__: Test}, CachedProject(project), CachedScene(scene))

    assert f"{const.name} = {const_value}" in src
    assert f"test_name.{Test.test_par.__name__}({const.name}, an='ac1')" in src

@pytest.mark.repeat(10)
def test_blind_branch() -> None:

    scene = Scene("s1")
    obj = SceneObject("test_name", Test.__name__)
    scene.objects.append(obj)
    project = Project("p1", "s1")
    ap1 = ActionPoint("ap1", Position())
    project.action_points.append(ap1)

    ac1 = Action("ac1", f"{obj.id}/test", flows=[Flow(outputs=["bool_res"])])
    ap1.actions.append(ac1)

    ac2 = Action("ac2", f"{obj.id}/test", flows=[Flow()])
    ap1.actions.append(ac2)

    ac3 = Action("ac3", f"{obj.id}/test", flows=[Flow()])
    ap1.actions.append(ac3)

    ac4 = Action("ac4", f"{obj.id}/test", flows=[Flow()])
    ap1.actions.append(ac4)

    project.logic.append(LogicItem(LogicItem.START, ac1.id))

    project.logic.append(LogicItem(ac1.id, ac2.id, ProjectLogicIf(f"{ac1.id}/default/0", json.dumps(True))))
    project.logic.append(LogicItem(ac1.id, ac3.id, ProjectLogicIf(f"{ac1.id}/default/0", json.dumps(False))))

    project.logic.append(LogicItem(ac2.id, ac4.id))
    project.logic.append(LogicItem(ac4.id, LogicItem.END))

    with pytest.raises(SourceException, match=f"Action {ac3.name} has no outputs."):
        src= program_src({Test.__name__: Test}, CachedProject(project), CachedScene(scene))

@pytest.mark.repeat(10)
def test_branched_output() -> None:

    scene = Scene("s1")
    obj = SceneObject("test_name", "Test")
    scene.objects.append(obj)
    project = Project("p1", "s1")
    ap1 = ActionPoint("ap1", Position())
    project.action_points.append(ap1)

    ac1 = Action("ac1", f"{obj.id}/test", flows=[Flow(outputs=["bool_res"])])
    ap1.actions.append(ac1)

    ac2 = Action("ac2", f"{obj.id}/test", flows=[Flow()])
    ap1.actions.append(ac2)

    ac3 = Action("ac3", f"{obj.id}/test", flows=[Flow()])
    ap1.actions.append(ac3)

    ac4 = Action("ac4", f"{obj.id}/test", flows=[Flow()])
    ap1.actions.append(ac4)

    project.logic.append(LogicItem(LogicItem.START, ac1.id))

    project.logic.append(LogicItem(ac1.id, ac2.id, ProjectLogicIf(f"{ac1.id}/default/0", json.dumps(True))))
    project.logic.append(LogicItem(ac1.id, ac3.id, ProjectLogicIf(f"{ac1.id}/default/0", json.dumps(False))))

    project.logic.append(LogicItem(ac2.id, ac4.id))
    project.logic.append(LogicItem(ac3.id, ac4.id))
    project.logic.append(LogicItem(ac4.id, LogicItem.END))

    src = program_src({Test.__name__: Test}, CachedProject(project), CachedScene(scene))

    parse(src)



    """
    bool_res = test_name.test(res.ac1)
    if bool_res == False:
        test_name.test(res.ac3)
    elif bool_res == True:
        test_name.test(res.ac2)
    test_name.test(res.ac4)
    """

    spl = src.splitlines()

    ac1_idx = subs_index(spl, "bool_res = test_name.test(an='ac1')")

    if_bool_res_false_idx = subs_index(spl, "if bool_res == False:")
    assert if_bool_res_false_idx > ac1_idx
    assert cntsp(spl[if_bool_res_false_idx]) == cntsp(spl[ac1_idx])
    assert "test_name.test(an='ac3')" in spl[if_bool_res_false_idx + 1]
    assert cntsp(spl[if_bool_res_false_idx]) == cntsp(spl[if_bool_res_false_idx + 1]) - TAB

    if_bool_res_true_idx = subs_index(spl, "if bool_res == True:")
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

    scene = Scene("s1")
    obj = SceneObject("test_name", Test.__name__)
    scene.objects.append(obj)
    project = Project("p1", "s1")
    ap1 = ActionPoint("ap1", Position())
    project.action_points.append(ap1)

    ac1 = Action("ac1", f"{obj.id}/test", flows=[Flow(outputs=["bool_res"])])
    ap1.actions.append(ac1)

    ac2 = Action("ac2", f"{obj.id}/test", flows=[Flow()])
    ap1.actions.append(ac2)

    ac3 = Action("ac3", f"{obj.id}/test", flows=[Flow()])
    ap1.actions.append(ac3)

    ac4 = Action("ac4", f"{obj.id}/test", flows=[Flow(outputs=["bool2_res"])])
    ap1.actions.append(ac4)

    ac5 = Action("ac5", f"{obj.id}/test", flows=[Flow()])
    ap1.actions.append(ac5)

    ac6 = Action("ac6", f"{obj.id}/test", flows=[Flow()])
    ap1.actions.append(ac6)

    project.logic.append(LogicItem(LogicItem.START, ac1.id))

    project.logic.append(LogicItem(ac1.id, ac2.id, ProjectLogicIf(f"{ac1.id}/default/0", json.dumps(True))))
    project.logic.append(LogicItem(ac1.id, ac4.id, ProjectLogicIf(f"{ac1.id}/default/0", json.dumps(False))))

    project.logic.append(LogicItem(ac2.id, ac3.id))
    project.logic.append(LogicItem(ac3.id, ac6.id))

    project.logic.append(LogicItem(ac4.id, ac5.id, ProjectLogicIf(f"{ac4.id}/default/0", json.dumps(True))))
    project.logic.append(LogicItem(ac5.id, ac6.id))
    project.logic.append(LogicItem(ac6.id, LogicItem.END))

    project.logic.append(LogicItem(ac4.id, LogicItem.END, ProjectLogicIf(f"{ac4.id}/default/0", json.dumps(False))))

    src = program_src({Test.__name__: Test}, CachedProject(project), CachedScene(scene))
    parse(src)

    """
    bool_res = test_name.test(res.ac1)
    if bool_res == False:
        bool2_res = test_name.test(res.ac4)
        if bool2_res == False:
            continue
        elif bool2_res == True:
            test_name.test(res.ac5)
    elif bool_res == True:
        test_name.test(res.ac2)
        test_name.test(res.ac3)
    test_name.test(res.ac6)
    """

    spl = src.splitlines()

    # it has to be robust against changed order of blocks
    ac1_idx = subs_index(spl, "bool_res = test_name.test(an='ac1')")

    if_bool_res_false_idx = subs_index(spl, "if bool_res == False:")
    assert if_bool_res_false_idx > ac1_idx
    assert cntsp(spl[ac1_idx]) == cntsp(spl[if_bool_res_false_idx])

    bool2_res_idx = subs_index(spl, "bool2_res = test_name.test(an='ac4')")
    assert bool2_res_idx > if_bool_res_false_idx
    assert cntsp(spl[if_bool_res_false_idx]) == cntsp(spl[bool2_res_idx]) - TAB

    if_bool_2_res_false_idx = subs_index(spl, "if bool2_res == False:")
    assert cntsp(spl[if_bool_2_res_false_idx]) == cntsp(spl[bool2_res_idx])
    assert if_bool_2_res_false_idx > bool2_res_idx
    assert "continue" in spl[if_bool_2_res_false_idx + 1]
    assert cntsp(spl[bool2_res_idx]) == cntsp(spl[if_bool_2_res_false_idx + 1]) - TAB

    if_bool_2_res_true_idx = subs_index(spl, "if bool2_res == True:")
    assert if_bool_2_res_true_idx > bool2_res_idx
    assert "test_name.test(an='ac5')" in spl[if_bool_2_res_true_idx + 1]
    assert cntsp(spl[if_bool_2_res_true_idx]) == cntsp(spl[if_bool_2_res_true_idx + 1]) - TAB

    if_bool_res_true_idx = subs_index(spl, "if bool_res == True:")
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