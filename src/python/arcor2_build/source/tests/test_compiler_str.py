import json

from arcor2.cached import CachedProject
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
from arcor2.exceptions import Arcor2Exception
from arcor2_build.source.python_to_json import python_to_json
from arcor2_build.source.tests.test_logic import Test

head = """#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from object_types.test import Test
from action_points import ActionPoints
from arcor2_runtime.resources import Resources
from arcor2_runtime.exceptions import print_exception"""

main = """def main(res: Resources) -> None:
    aps = ActionPoints(res)
    test_name: Test = res.objects['obj_392f80383d41481ab910dfebcee813c6']"""

call_main = """if __name__ == '__main__':
    try:
        with Resources() as res:
            main(res)
    except Exception as e:
        print_exception(e)"""


def action_from_id(id: str, project: CachedProject) -> Action:  # TODO: replace

    for action in project.actions:
        if id == action.id:
            return action
    raise Arcor2Exception("Action whit name:" + id + " in project:" + project.name + "does not exisit")


def check_python_to_json(project: Project, scene: Scene, script: str, objects_for_json: dict):

    o_p = CachedProject(project)
    original_project = project.copy()

    modified_project = python_to_json(original_project, scene, script, objects_for_json)
    m_p = CachedProject(modified_project)

    assert (len(o_p.actions)) == (len(m_p.actions))
    assert (len(o_p.logic)) == (len(m_p.logic))

    start_modified_action: Action
    end_modif_action: Action
    start_orig_action: Action
    start_orig_action_id = ""
    end_orig_action: Action
    end_orig_action_id = ""
    orig_logic_item: LogicItem
    for modif_logic_item in m_p.logic:

        if modif_logic_item.start != LogicItem.START:
            start_modified_action = action_from_id(modif_logic_item.start, m_p)
            start_orig_action = o_p.action_from_name(start_modified_action.name)
            assert start_modified_action.name == start_orig_action.name  # name
            assert start_modified_action.type == start_orig_action.type  # type
            assert start_modified_action.flows == start_orig_action.flows  # flow

            if start_modified_action.parameters:  # param
                for i in range(len(start_modified_action.parameters)):
                    assert (
                        start_modified_action.parameters[i].type == start_orig_action.parameters[i].type
                    )  # param type
                    assert (
                        start_modified_action.parameters[i].name == start_orig_action.parameters[i].name
                    )  # param name
                    # TODO: vlaue
            else:
                assert start_orig_action.parameters == []

            start_orig_action_id = start_orig_action.id  # save id
        else:
            start_orig_action_id = LogicItem.START  # save id

        if modif_logic_item.end != LogicItem.END:
            end_modif_action = action_from_id(modif_logic_item.end, m_p)
            end_orig_action = o_p.action_from_name(end_modif_action.name)
            assert end_modif_action.name == end_orig_action.name  # name
            assert end_modif_action.type == end_orig_action.type  # type
            assert end_modif_action.flows == end_orig_action.flows  # flow

            if end_modif_action.parameters:  # param
                for i in range(len(end_modif_action.parameters)):
                    assert end_modif_action.parameters[i].type == end_orig_action.parameters[i].type  # param type
                    assert end_modif_action.parameters[i].name == end_orig_action.parameters[i].name  # param name
                    # TODO: vlaue
            else:
                assert end_orig_action.parameters == []

            end_orig_action_id = end_orig_action.id  # save id
        else:
            end_orig_action_id = LogicItem.END  # save id

        orig_logic_item = o_p.find_logic_start_end(start_orig_action_id, end_orig_action_id)
        if modif_logic_item.condition and isinstance(orig_logic_item.condition, ProjectLogicIf):
            assert modif_logic_item.condition.value == orig_logic_item.condition.value  # value(flase, true,...)

            tmp1 = modif_logic_item.condition.what
            tmp2 = orig_logic_item.condition.what

            tmp1 = tmp1.removesuffix("/default/0")
            tmp2 = tmp2.removesuffix("/default/0")

            modif_con = action_from_id(tmp1, m_p)  # action where was declared variable in modif_project
            orig_con = action_from_id(tmp2, o_p)  # action where was declared variable in orig_project
            assert modif_con.name == orig_con.name  # action name
            assert modif_con.type == orig_con.type  # action type
            assert modif_con.flows == orig_con.flows  # action flow


def test_little() -> None:

    scene = Scene("s1")
    obj = SceneObject("test_name", Test.__name__)
    scene.objects.append(obj)
    project = Project("p1", "s1")
    ap1 = ActionPoint("ap1", Position())
    project.action_points.append(ap1)

    project.logic.append(LogicItem(LogicItem.START, LogicItem.END))

    script = f"""
{head}


{main}
    while True:
        continue


{call_main}"""

    check_python_to_json(project, scene, script, {"test_name": Test})


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

    script = f"""
{head}


{main}
    while True:
        res = test_name.get_int(an='ac1')
        test_name.test_par(res, an='ac2')


{call_main}"""

    check_python_to_json(project, scene, script, {"test_name": Test})


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

    script = f"""
{head}


{main}
    int_const = 1234
    while True:
        test_name.test_par(int_const, an='ac1')


{call_main}"""

    check_python_to_json(project, scene, script, {"test_name": Test})


def test_branched_output1() -> None:

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

    script = f"""
{head}


{main}
    while True:
        bool_res = test_name.test(an='ac1')
        if bool_res == True:
            test_name.test(an='ac2')
        elif bool_res == False:
            test_name.test(an='ac3')
        test_name.test(an='ac4')


{call_main}"""

    check_python_to_json(project, scene, script, {"test_name": Test})


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

    script = f"""
{head}


{main}
    while True:
        bool_res = test_name.test(an='ac1')
        if bool_res == True:
            test_name.test(an='ac2')
            test_name.test(an='ac3')
        elif bool_res == False:
            bool2_res = test_name.test(an='ac4')
            if bool2_res == True:
                test_name.test(an='ac5')
            elif bool2_res == False:
                continue
        test_name.test(an='ac6')


{call_main}"""

    check_python_to_json(project, scene, script, {"test_name": Test})


def test_branched_output_3() -> None:

    scene = Scene("s1")
    obj = SceneObject("test_name", Test.__name__)
    scene.objects.append(obj)
    project = Project("p1", "s1")
    ap1 = ActionPoint("ap1", Position())
    project.action_points.append(ap1)

    ac1 = Action("ac1", f"{obj.id}/test", flows=[Flow(outputs=["bool1_res"])])
    ap1.actions.append(ac1)

    ac2 = Action("ac2", f"{obj.id}/test", flows=[Flow(outputs=["bool2_res"])])
    ap1.actions.append(ac2)

    ac3 = Action("ac3", f"{obj.id}/test", flows=[Flow(outputs=["bool3_res"])])
    ap1.actions.append(ac3)

    ac4 = Action("ac4", f"{obj.id}/test", flows=[Flow(outputs=["bool4_res"])])
    ap1.actions.append(ac4)

    ac5 = Action("ac5", f"{obj.id}/test", flows=[Flow()])
    ap1.actions.append(ac5)

    ac6 = Action("ac6", f"{obj.id}/test", flows=[Flow()])
    ap1.actions.append(ac6)

    ac7 = Action("ac7", f"{obj.id}/test", flows=[Flow()])
    ap1.actions.append(ac7)

    ac8 = Action("ac8", f"{obj.id}/test", flows=[Flow()])
    ap1.actions.append(ac8)

    ac9 = Action("ac9", f"{obj.id}/test", flows=[Flow()])
    ap1.actions.append(ac9)

    ac10 = Action("ac10", f"{obj.id}/test", flows=[Flow()])
    ap1.actions.append(ac10)

    project.logic.append(LogicItem(LogicItem.START, ac1.id))

    project.logic.append(LogicItem(ac1.id, ac2.id, ProjectLogicIf(f"{ac1.id}/default/0", json.dumps(True))))
    project.logic.append(LogicItem(ac2.id, ac3.id, ProjectLogicIf(f"{ac2.id}/default/0", json.dumps(True))))
    project.logic.append(LogicItem(ac3.id, ac4.id, ProjectLogicIf(f"{ac3.id}/default/0", json.dumps(True))))
    project.logic.append(LogicItem(ac4.id, ac5.id, ProjectLogicIf(f"{ac4.id}/default/0", json.dumps(True))))
    project.logic.append(LogicItem(ac5.id, ac10.id))

    project.logic.append(LogicItem(ac1.id, ac9.id, ProjectLogicIf(f"{ac1.id}/default/0", json.dumps(False))))
    project.logic.append(LogicItem(ac9.id, ac10.id))

    project.logic.append(LogicItem(ac2.id, ac8.id, ProjectLogicIf(f"{ac2.id}/default/0", json.dumps(False))))
    project.logic.append(LogicItem(ac8.id, ac10.id))

    project.logic.append(LogicItem(ac3.id, ac7.id, ProjectLogicIf(f"{ac3.id}/default/0", json.dumps(False))))
    project.logic.append(LogicItem(ac7.id, ac10.id))

    project.logic.append(LogicItem(ac4.id, ac6.id, ProjectLogicIf(f"{ac4.id}/default/0", json.dumps(False))))
    project.logic.append(LogicItem(ac6.id, ac10.id))

    project.logic.append(LogicItem(ac10.id, LogicItem.END))

    script = f"""
{head}


{main}
    while True:
        bool1_res = test_name.test(an='ac1')
        if bool1_res == True:
            bool2_res = test_name.test(an='ac2')
            if bool2_res == True:
                bool3_res = test_name.test(an='ac3')
                if bool3_res == True:
                    bool4_res = test_name.test(an='ac4')
                    if bool4_res == True:
                        test_name.test(an='ac5')
                    elif bool4_res == False:
                        test_name.test(an='ac6')
                elif bool3_res == False:
                    test_name.test(an='ac7')
            elif bool2_res == False:
                test_name.test(an='ac8')
        elif bool1_res == False:
            test_name.test(an='ac9')
        test_name.test(an='ac10')


{call_main}"""

    check_python_to_json(project, scene, script, {"test_name": Test})


def test_branched_output_4() -> None:

    scene = Scene("s1")
    obj = SceneObject("test_name", Test.__name__)
    scene.objects.append(obj)
    project = Project("p1", "s1")
    ap1 = ActionPoint("ap1", Position())
    project.action_points.append(ap1)

    ac1 = Action("ac1", f"{obj.id}/test", flows=[Flow(outputs=["bool1_res"])])
    ap1.actions.append(ac1)

    ac2 = Action("ac2", f"{obj.id}/test", flows=[Flow(outputs=["bool2_res"])])
    ap1.actions.append(ac2)

    ac3 = Action("ac3", f"{obj.id}/test", flows=[Flow(outputs=["bool3_res"])])
    ap1.actions.append(ac3)

    ac4 = Action("ac4", f"{obj.id}/test", flows=[Flow(outputs=["bool4_res"])])
    ap1.actions.append(ac4)

    ac5 = Action("ac5", f"{obj.id}/test", flows=[Flow()])
    ap1.actions.append(ac5)

    ac9 = Action("ac9", f"{obj.id}/test", flows=[Flow()])
    ap1.actions.append(ac9)

    ac10 = Action("ac10", f"{obj.id}/test", flows=[Flow()])
    ap1.actions.append(ac10)

    project.logic.append(LogicItem(LogicItem.START, ac1.id))

    project.logic.append(LogicItem(ac1.id, ac2.id, ProjectLogicIf(f"{ac1.id}/default/0", json.dumps(True))))
    project.logic.append(LogicItem(ac2.id, ac3.id, ProjectLogicIf(f"{ac2.id}/default/0", json.dumps(True))))
    project.logic.append(LogicItem(ac3.id, ac4.id, ProjectLogicIf(f"{ac3.id}/default/0", json.dumps(True))))
    project.logic.append(LogicItem(ac4.id, ac5.id, ProjectLogicIf(f"{ac4.id}/default/0", json.dumps(True))))
    project.logic.append(LogicItem(ac5.id, ac10.id))

    project.logic.append(LogicItem(ac1.id, ac9.id, ProjectLogicIf(f"{ac1.id}/default/0", json.dumps(False))))
    project.logic.append(LogicItem(ac9.id, ac10.id))

    project.logic.append(LogicItem(ac2.id, LogicItem.END, ProjectLogicIf(f"{ac2.id}/default/0", json.dumps(False))))
    project.logic.append(LogicItem(ac3.id, LogicItem.END, ProjectLogicIf(f"{ac3.id}/default/0", json.dumps(False))))
    project.logic.append(LogicItem(ac4.id, LogicItem.END, ProjectLogicIf(f"{ac4.id}/default/0", json.dumps(False))))

    project.logic.append(LogicItem(ac10.id, LogicItem.END))

    script = f"""
{head}


{main}
    while True:
        bool1_res = test_name.test(an='ac1')
        if bool1_res == True:
            bool2_res = test_name.test(an='ac2')
            if bool2_res == True:
                bool3_res = test_name.test(an='ac3')
                if bool3_res == True:
                    bool4_res = test_name.test(an='ac4')
                    if bool4_res == True:
                        test_name.test(an='ac5')
                    elif bool4_res == False:
                        continue
                elif bool3_res == False:
                    continue
            elif bool2_res == False:
                continue
        elif bool1_res == False:
            test_name.test(an='ac9')
        test_name.test(an='ac10')


{call_main}"""

    check_python_to_json(project, scene, script, {"test_name": Test})
