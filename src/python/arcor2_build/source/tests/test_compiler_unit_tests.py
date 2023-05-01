import ast
import inspect
import json
from ast import If
from copy import deepcopy

import pytest

from arcor2.cached import CachedProject, CachedScene
from arcor2.data.common import (
    Action,
    ActionParameter,
    ActionPoint,
    Flow,
    Joint,
    LogicItem,
    NamedOrientation,
    Orientation,
    Pose,
    Position,
    Project,
    ProjectLogicIf,
    ProjectParameter,
    ProjectRobotJoints,
    Scene,
    SceneObject,
    StrEnum,
)
from arcor2.exceptions import Arcor2Exception
from arcor2.object_types.abstract import Generic
from arcor2.parameter_plugins.utils import plugin_from_type
from arcor2_build.source.python_to_json import (
    evaluate_if,
    evaluate_nodes,
    gen_action,
    gen_logic,
    gen_logic_after_if,
    gen_logic_for_if,
    get_parameters,
)
from arcor2_build.source.utils import find_Call


class TestEnum(StrEnum):
    CLASS1: str = "1"
    CLASS2: str = "2"


class Test(Generic):
    INT = 1234

    def get_int(self, an: None | str = None) -> int:
        return self.INT

    def test(self, an: None | str = None) -> bool:
        return True

    def test_two_values(self, an: None | str = None) -> tuple[bool, bool]:
        return True, False

    def test_par(self, param: int, an: None | str = None) -> None:
        pass

    def test_pose(self, param: Pose, an: None | str = None) -> None:
        pass

    def test_joints(self, param: ProjectRobotJoints, an: None | str = None) -> None:
        pass

    def test_position(self, param: Position, an: None | str = None) -> None:
        pass

    def tests_class_value(self, param: TestEnum, an: None | str = None):
        pass

    def test_all(
        self,
        param: TestEnum,
        joint: ProjectRobotJoints,
        pose: Pose,
        int_param1: int,
        int_param2: int,
        int_param3: int,
        an: None | str = None,
    ):
        pass


scene = Scene("s1")
scene.objects.append(SceneObject("test", Test.__name__))
c_s = CachedScene(scene)

project = Project("p1", "s1")
ap1 = ActionPoint(
    "ap1",
    Position(1.1, 0.0, -1.1),
    None,
    None,
    None,
    "",
    orientations=([NamedOrientation("default", Orientation(2.2, 0.0, -2.2))]),
    robot_joints=(
        [ProjectRobotJoints("default", "", [Joint("Joint1", 3.3), Joint("Joint2", 0.0), Joint("Joint3", -3.3)])]
    ),
)
project.action_points.append(ap1)

const = ProjectParameter("int_const", "integer", json.dumps(1234))
project.parameters.append(const)


def test_gen_logic() -> None:
    logic_list = []
    item = LogicItem("1", "")
    logic_list.append(item)

    gen_logic("2", logic_list)

    assert len(logic_list) == 2

    assert logic_list[0].start == "1"
    assert logic_list[0].end == "2"

    assert logic_list[1].start == "2"
    assert logic_list[1].end == ""


def test_gen_logic_for_if() -> None:
    logic_list: list[LogicItem] = []

    gen_logic_for_if("1", logic_list)

    assert len(logic_list) == 1

    assert logic_list[0].start == "1"
    assert logic_list[0].end == ""


def test_gen_logic_after_if() -> None:
    logic_list = []
    item = LogicItem("1", "")
    logic_list.append(item)

    item = LogicItem("2", "4")
    logic_list.append(item)

    item = LogicItem("3", "")
    logic_list.append(item)

    gen_logic_after_if("5", logic_list)

    assert len(logic_list) == 4

    assert logic_list[0].start == "1"
    assert logic_list[0].end == "5"

    assert logic_list[1].start == "2"
    assert logic_list[1].end == "4"

    assert logic_list[2].start == "3"
    assert logic_list[2].end == "5"

    assert logic_list[3].start == "5"
    assert logic_list[3].end == ""


def test_get_object_by_name1() -> None:
    # usual case
    id_method1 = c_s.get_object_by_name("test.test")
    assert id_method1 == f"{next(c_s.objects).id}/test"


def test_get_object_by_name2() -> None:
    # usual case
    id_method2 = c_s.get_object_by_name("test.test_pose")
    assert id_method2 == f"{next(c_s.objects).id}/test_pose"


def test_get_object_by_name3() -> None:
    # non-existent object
    try:
        c_s.get_object_by_name("non-existent_object_.method")
        AssertionError()
    except Arcor2Exception:
        assert True


def test_get_parameters1() -> None:
    # project parameter
    ap_another = ActionPoint("another", Position())
    call_node = find_Call(ast.parse('test.test_par(int_const,an="ac1")'))
    method = inspect.getfullargspec(Test.test_par)
    parmeters, ap = get_parameters(call_node, {}, project, ap_another, method)

    assert parmeters[0] == ActionParameter("param", ActionParameter.TypeEnum.PROJECT_PARAMETER, json.dumps(const.id))
    assert ap == ap_another


def test_get_parameters2() -> None:
    # constant
    ap_another = ActionPoint("another", Position())
    call_node = find_Call(ast.parse('test.test_par(42,an="ac1")'))
    method = inspect.getfullargspec(Test.test_par)
    parmeters, ap = get_parameters(call_node, {}, project, ap_another, method)

    assert parmeters[0] == ActionParameter("param", plugin_from_type(type(42)).type_name(), json.dumps(42))
    assert ap == ap_another


def test_get_parameters3() -> None:
    # variable
    ap_another = ActionPoint("another", Position())
    call_node = find_Call(ast.parse('test.test_par(variable,an="ac1")'))
    method = inspect.getfullargspec(Test.test_par)
    parmeters, ap = get_parameters(call_node, {"variable": "id123"}, project, ap_another, method)

    assert parmeters[0] == ActionParameter("param", ActionParameter.TypeEnum.LINK, json.dumps("id123/default/0"))
    assert ap == ap_another


def test_get_parameters4() -> None:
    # action_point_pose
    ap_another = ActionPoint("another", Position())
    call_node = find_Call(ast.parse('test.test_pose(aps.ap1.poses.default,an="ac1")'))
    method = inspect.getfullargspec(Test.test_pose)
    parmeters, ap = get_parameters(call_node, {}, project, ap_another, method)
    pose_type = plugin_from_type(Pose)

    assert parmeters[0] == ActionParameter("param", pose_type.type_name(), json.dumps(ap1.orientations[0].id))
    assert ap == ap1


def test_get_parameters5() -> None:
    # action_point_joints
    ap_another = ActionPoint("another", Position())
    call_node = find_Call(ast.parse('test.test_joints(aps.ap1.joints.default,an="ac1")'))
    method = inspect.getfullargspec(Test.test_joints)
    parmeters, ap = get_parameters(call_node, {}, project, ap_another, method)
    joints_type = plugin_from_type(ProjectRobotJoints)

    assert parmeters[0] == ActionParameter("param", joints_type.type_name(), json.dumps(ap1.robot_joints[0].id))
    assert ap == ap1


def test_get_parameters6() -> None:
    # action_point_position
    ap_another = ActionPoint("another", Position())
    call_node = find_Call(ast.parse('test.test_position(aps.ap1.position,an="ac1")'))
    method = inspect.getfullargspec(Test.test_position)
    parmeters, ap = get_parameters(call_node, {}, project, ap_another, method)
    position_type = plugin_from_type(Position)

    assert parmeters[0] == ActionParameter("param", position_type.type_name(), json.dumps(ap1.id))
    assert ap == ap1


def test_get_parameters7() -> None:
    # class value
    ap_another = ActionPoint("another", Position())
    call_node = find_Call(ast.parse('test.tests_class_value(TestEnum.CLASS2,an="ac1")'))
    method = inspect.getfullargspec(Test.tests_class_value)
    parmeters, ap = get_parameters(call_node, {}, project, ap_another, method)
    StrEnum_type = plugin_from_type(StrEnum)

    assert parmeters[0] == ActionParameter("param", StrEnum_type.type_name(), json.dumps(TestEnum.CLASS2))
    assert ap == ap_another


def test_get_parameters8() -> None:
    # all parameter types
    ap_another = ActionPoint("another", Position())
    StrEnum_type = plugin_from_type(StrEnum)
    joints_type = plugin_from_type(ProjectRobotJoints)
    pose_type = plugin_from_type(Pose)

    call_node = find_Call(
        ast.parse(
            """test.test_all(TestEnum.CLASS1, aps.ap1.joints.default, aps.ap1.poses.default, variable, 42,
            int_const, an="ac1")"""
        )
    )
    method = inspect.getfullargspec(Test.test_all)
    parmeters, ap = get_parameters(call_node, {"variable": "id123"}, project, ap_another, method)

    assert parmeters[0] == ActionParameter("param", StrEnum_type.type_name(), json.dumps(TestEnum.CLASS1))
    assert parmeters[1] == ActionParameter("joint", joints_type.type_name(), json.dumps(ap1.robot_joints[0].id))
    assert parmeters[2] == ActionParameter("pose", pose_type.type_name(), json.dumps(ap1.orientations[0].id))
    assert parmeters[3] == ActionParameter("int_param1", ActionParameter.TypeEnum.LINK, json.dumps("id123/default/0"))
    assert parmeters[4] == ActionParameter("int_param2", plugin_from_type(type(42)).type_name(), json.dumps(42))
    assert parmeters[5] == ActionParameter(
        "int_param3", ActionParameter.TypeEnum.PROJECT_PARAMETER, json.dumps(const.id)
    )
    assert ap == ap1


def test_get_parameters9() -> None:
    # too many parameters in method
    ap_another = ActionPoint("another", Position())
    call_node = find_Call(ast.parse('test.test_par(int_const, int_const, int_const, an="ac1")'))
    method = inspect.getfullargspec(Test.test_par)
    try:
        get_parameters(call_node, {}, project, ap_another, method)
        AssertionError()
    except Arcor2Exception:
        assert True


def test_get_parameters10() -> None:
    # not enought parameters in method
    ap_another = ActionPoint("another", Position())
    call_node = find_Call(ast.parse('test.test_par(an="ac1")'))
    method = inspect.getfullargspec(Test.test_par)
    try:
        get_parameters(call_node, {}, project, ap_another, method)
        AssertionError()
    except Arcor2Exception:
        assert True


def test_get_parameters11() -> None:
    # wrong constant value
    ap_another = ActionPoint("another", Position())
    call_node = find_Call(ast.parse('test.test_par("string",an="ac1")'))
    method = inspect.getfullargspec(Test.test_par)

    try:
        get_parameters(call_node, {}, project, ap_another, method)
        AssertionError()
    except Arcor2Exception:
        assert True


def test_get_parameters12() -> None:
    # non-existent variable
    ap_another = ActionPoint("another", Position())
    call_node = find_Call(ast.parse('test.test_par(variable,an="ac1")'))
    method = inspect.getfullargspec(Test.test_par)

    try:
        get_parameters(call_node, {}, project, ap_another, method)
        AssertionError()
    except Arcor2Exception:
        assert True


def test_get_parameters13() -> None:
    # non-existent action_point
    ap_another = ActionPoint("another", Position())
    call_node = find_Call(ast.parse('test.test_joints(aps.nothing.default,an="ac1")'))
    method = inspect.getfullargspec(Test.test_joints)

    try:
        get_parameters(call_node, {}, project, ap_another, method)
        AssertionError()
    except Arcor2Exception:
        assert True


def test_get_parameters14() -> None:
    # non-existent class attribute
    ap_another = ActionPoint("another", Position())
    call_node = find_Call(ast.parse('test.tests_class_value(TestEnum.nothing,an="ac1")'))
    method = inspect.getfullargspec(Test.tests_class_value)

    try:
        get_parameters(call_node, {}, project, ap_another, method)
        AssertionError()
    except Arcor2Exception:
        assert True


def test_get_parameters15() -> None:
    # non-existent class
    ap_another = ActionPoint("another", Position())
    call_node = find_Call(ast.parse('test.tests_class_value(Nothing.CLASS2,an="ac1")'))
    method = inspect.getfullargspec(Test.tests_class_value)

    try:
        get_parameters(call_node, {}, project, ap_another, method)
        AssertionError()
    except Arcor2Exception:
        assert True


def test_get_parameters16() -> None:
    # wrong parameter as action_point
    call_node = find_Call(ast.parse('test.tests_class_value(aps.ap1.position,an="ac1")'))
    method = inspect.getfullargspec(Test.tests_class_value)

    try:
        get_parameters(call_node, {}, project, ap1, method)
        AssertionError()
    except Arcor2Exception:
        assert True


def test_gen_action1() -> None:
    # basic case
    tree = ast.parse('test.test(an="ac1")')
    node = find_Call(tree)

    _ac1, variables, action_point = gen_action(
        ActionPoint("ap", Position()), node, {}, c_s, project, {"test": Test}, [], []
    )
    assert action_point.actions[0].name == "ac1"
    assert action_point.actions[0].type == f"{next(c_s.objects).id}/test"
    assert action_point.actions[0].parameters == []
    assert action_point.actions[0].flows == [Flow()]
    assert variables == {}


def test_gen_action2() -> None:
    # case with output
    tree = ast.parse('variable = test.test(an="ac1")')
    node = find_Call(tree)

    ac1, variables, action_point = gen_action(
        ActionPoint("ap", Position()), node, {}, c_s, project, {"test": Test}, ["variable"], []
    )
    assert action_point.actions[0].name == "ac1"
    assert action_point.actions[0].type == f"{next(c_s.objects).id}/test"
    assert action_point.actions[0].parameters == []
    assert action_point.actions[0].flows == [Flow(outputs=["variable"])]
    assert variables == {"variable": ac1}


def test_gen_action3() -> None:
    # case with output
    tree = ast.parse('variable1, vriable2 = test.test_two_values(an="ac1")')
    node = find_Call(tree)

    ac1, variables, action_point = gen_action(
        ActionPoint("ap", Position()), node, {}, c_s, project, {"test": Test}, ["variable1", "variable2"], []
    )
    assert action_point.actions[0].name == "ac1"
    assert action_point.actions[0].type == f"{next(c_s.objects).id}/test_two_values"
    assert action_point.actions[0].parameters == []
    assert action_point.actions[0].flows == [Flow(outputs=["variable1"]), Flow(outputs=["variable2"])]
    assert variables == {"variable1": ac1, "variable2": ac1}


def test_gen_action4() -> None:
    # case with parameter
    tree = ast.parse('variable = test.test_par(variable,an="ac1")')
    node = find_Call(tree)

    _ac1, variables, action_point = gen_action(
        ActionPoint("ap", Position()), node, {"variable": "id123"}, c_s, project, {"test": Test}, [], []
    )
    assert action_point.actions[0].name == "ac1"
    assert action_point.actions[0].type == f"{next(c_s.objects).id}/test_par"
    assert action_point.actions[0].parameters == [
        ActionParameter("param", ActionParameter.TypeEnum.LINK, json.dumps("id123/default/0"))
    ]
    assert action_point.actions[0].flows == [Flow()]
    assert variables == {"variable": "id123"}


def test_gen_action5() -> None:
    # non-existent method
    tree = ast.parse('test.nothing(an="ac1")')
    node = find_Call(tree)

    try:
        gen_action(ActionPoint("ap", Position()), node, {}, c_s, project, {"test": Test}, [], [])
        AssertionError()
    except Arcor2Exception:
        assert True


def test_gen_action6() -> None:
    # missing "an"
    tree = ast.parse("test.test()")
    node = find_Call(tree)

    try:
        gen_action(ActionPoint("ap", Position()), node, {}, c_s, project, {"test": Test}, [], [])
        AssertionError()
    except Arcor2Exception:
        assert True


def test_gen_action7() -> None:
    # missing "an" version2
    tree = ast.parse('test.test(something="ac1")')
    node = find_Call(tree)

    try:
        gen_action(ActionPoint("ap", Position()), node, {}, c_s, project, {"test": Test}, [], [])
        AssertionError()
    except Arcor2Exception:
        assert True


def test_evaluate_if1() -> None:
    # usual case
    project2 = Project("p1", "s1")
    ap_another = ActionPoint("ap_another", Position())
    project2.action_points.append(ap_another)

    ac1 = Action("ac1", f"{next(c_s.objects).id}/test", flows=[Flow(outputs=["bool_res1"])])
    ap_another.actions.append(ac1)
    project2.logic.append(LogicItem(LogicItem.START, ac1.id))

    tree = ast.parse(
        """
if bool_res1 == True:
    test.test(an='ac2')
elif bool_res1 == False:
    test.test(an='ac3')"""
    )
    if isinstance(tree.body[0], If):
        node = tree.body[0]

    variables = evaluate_if(
        ap_another, node, {"bool_res1": "id123", "bool_res2": "id456"}, ac1.id, c_s, project2, {"test": Test}, []
    )

    tmp_project = CachedProject(project2)
    assert variables == {"bool_res1": "id123", "bool_res2": "id456"}
    assert len(tmp_project.actions) == 3
    assert len(tmp_project.logic) == 5
    assert project2.logic[0].start == "START"
    assert project2.logic[0].end == ac1.id

    assert project2.logic[1].start == ac1.id
    assert project2.logic[1].condition == ProjectLogicIf("id123/default/0", json.dumps(True))
    assert project2.logic[2].end == ""

    assert project2.logic[3].start == ac1.id
    assert project2.logic[3].condition == ProjectLogicIf("id123/default/0", json.dumps(False))
    assert project2.logic[4].end == ""


def test_evaluate_if2() -> None:
    # "if" without "elif"
    project2 = Project("p1", "s1")
    ap_another = ActionPoint("ap_another", Position())
    project2.action_points.append(ap_another)

    ac1 = Action("ac1", f"{next(c_s.objects).id}/test", flows=[Flow(outputs=["bool_res1"])])
    ap_another.actions.append(ac1)
    project2.logic.append(LogicItem(LogicItem.START, ac1.id))

    tree = ast.parse(
        """
if bool_res1 == True:
    test.test(an='ac2')"""
    )
    if isinstance(tree.body[0], If):
        node = tree.body[0]

    variables = evaluate_if(ap_another, node, {"bool_res1": "id123"}, ac1.id, c_s, project2, {"test": Test}, [])

    tmp_project = CachedProject(project2)
    assert variables == {"bool_res1": "id123"}
    assert len(tmp_project.actions) == 2
    assert len(tmp_project.logic) == 3
    assert project2.logic[0].start == "START"
    assert project2.logic[0].end == ac1.id

    assert project2.logic[1].start == ac1.id
    assert project2.logic[1].condition == ProjectLogicIf("id123/default/0", json.dumps(True))
    assert project2.logic[2].end == ""


def test_evaluate_if3() -> None:
    # "if" in "if" without method between
    project2 = Project("p1", "s1")
    ap_another = ActionPoint("ap_another", Position())
    project2.action_points.append(ap_another)

    ac1 = Action("ac1", f"{next(c_s.objects).id}/test", flows=[Flow(outputs=["bool_res1"])])
    ap1.actions.append(ac1)

    project2.logic.append(LogicItem(LogicItem.START, ac1.id))
    project2.logic.append(LogicItem(ac1.id, ""))

    tree = ast.parse(
        """
if bool_res1 == True:
    if bool_res2 == True:
        test.test(an='ac2')
elif bool_res1 == False:
    test.test(an='ac3')"""
    )
    if isinstance(tree.body[0], If):
        node = tree.body[0]

    try:
        evaluate_if(ap1, node, {"bool_res1": "id123", "bool_res2": "id456"}, ac1.id, c_s, project2, {"test": Test}, [])
        AssertionError()
    except Arcor2Exception:
        assert True


def test_evaluate_if4() -> None:
    # more conditions in "if"
    project2 = Project("p1", "s1")
    ap_another = ActionPoint("ap_another", Position())
    project2.action_points.append(ap_another)

    ac1 = Action("ac1", f"{next(c_s.objects).id}/test", flows=[Flow(outputs=["bool_res1"])])
    ap1.actions.append(ac1)

    project2.logic.append(LogicItem(LogicItem.START, ac1.id))
    project2.logic.append(LogicItem(ac1.id, ""))

    tree = ast.parse(
        """
if bool_res1 == True and bool_res2 == True:
    test.test(an='ac2')
elif bool_res1 == False:
    test.test(an='ac3')"""
    )
    if isinstance(tree.body[0], If):
        node = tree.body[0]
    try:
        evaluate_if(ap1, node, {"bool_res1": "id123", "bool_res2": "id456"}, ac1.id, c_s, project2, {"test": Test}, [])
        AssertionError()
    except Arcor2Exception:
        assert True


def test_evaluate_if5() -> None:
    # condition is value
    project2 = Project("p1", "s1")
    ap_another = ActionPoint("ap_another", Position())
    project2.action_points.append(ap_another)

    ac1 = Action("ac1", f"{next(c_s.objects).id}/test", flows=[Flow(outputs=["bool_res1"])])
    ap1.actions.append(ac1)

    project2.logic.append(LogicItem(LogicItem.START, ac1.id))
    project2.logic.append(LogicItem(ac1.id, ""))

    tree = ast.parse(
        """
if True:
    test.test(an='ac2')
elif bool_res1 == False:
    test.test(an='ac3')"""
    )
    if isinstance(tree.body[0], If):
        node = tree.body[0]
    try:
        evaluate_if(ap1, node, {"bool_res1": "id123"}, ac1.id, c_s, project2, {"test": Test}, [])
        AssertionError()
    except Arcor2Exception:
        assert True


def test_evaluate_if6() -> None:
    # non-existent variable
    project2 = Project("p1", "s1")
    ap_another = ActionPoint("ap_another", Position())
    project2.action_points.append(ap_another)

    ac1 = Action("ac1", f"{next(c_s.objects).id}/test", flows=[Flow(outputs=["bool_res1"])])
    ap1.actions.append(ac1)

    project2.logic.append(LogicItem(LogicItem.START, ac1.id))
    project2.logic.append(LogicItem(ac1.id, ""))

    tree = ast.parse(
        """
if variable == True:
    test.test(an='ac2')
elif bool_res1 == False:
    test.test(an='ac3')"""
    )
    if isinstance(tree.body[0], If):
        node = tree.body[0]
    try:
        evaluate_if(ap1, node, {"bool_res1": "id123"}, ac1.id, c_s, project2, {"test": Test}, [])
        AssertionError()
    except Arcor2Exception:
        assert True


def test_evaluate_if7() -> None:
    # condition is method
    project2 = Project("p1", "s1")
    ap_another = ActionPoint("ap_another", Position())
    project2.action_points.append(ap_another)

    ac1 = Action("ac1", f"{next(c_s.objects).id}/test", flows=[Flow(outputs=["bool_res1"])])
    ap1.actions.append(ac1)

    project2.logic.append(LogicItem(LogicItem.START, ac1.id))
    project2.logic.append(LogicItem(ac1.id, ""))

    tree = ast.parse(
        """
if test.test(an='ac4'):
    test.test(an='ac2')
elif bool_res1 == False:
    test.test(an='ac3')"""
    )
    if isinstance(tree.body[0], If):
        node = tree.body[0]
    try:
        evaluate_if(ap1, node, {"bool_res1": "id123"}, ac1.id, c_s, project2, {"test": Test}, [])
        AssertionError()
    except Arcor2Exception:
        assert True


def test_evaluate_nodes1() -> None:
    # action_point mix
    project2 = Project("p1", "s1")
    ap_another1 = ActionPoint(
        "ap_another1",
        Position(1.1, 0.0, -1.1),
    )
    ap_another2 = ActionPoint(
        "ap_another2",
        Position(2.2, 0.0, -2.2),
    )
    ap_another3 = ActionPoint(
        "ap_another3",
        Position(3.3, 0.0, -3.3),
    )

    project2.action_points.append(deepcopy(ap_another1))
    project2.action_points.append(deepcopy(ap_another2))
    project2.action_points.append(deepcopy(ap_another3))

    ac1 = Action("ac1", f"{next(c_s.objects).id}/test", flows=[Flow()])
    ap_another1.actions.append(ac1)

    ac2 = Action("ac2", f"{next(c_s.objects).id}/test", flows=[Flow()])
    ap_another2.actions.append(ac2)

    ac3 = Action("ac3", f"{next(c_s.objects).id}/test", flows=[Flow()])
    ap_another3.actions.append(ac3)

    ac4 = Action("ac4", f"{next(c_s.objects).id}/test", flows=[Flow()])
    ap_another1.actions.append(ac4)

    ac5 = Action("ac5", f"{next(c_s.objects).id}/test", flows=[Flow()])
    ap_another2.actions.append(ac5)

    ac6 = Action("ac6", f"{next(c_s.objects).id}/test", flows=[Flow()])
    ap_another3.actions.append(ac6)

    project2.logic.append(LogicItem(LogicItem.START, LogicItem.END))

    node = ast.parse(
        """
test.test(an='ac1')
test.test(an='ac2')
test.test_position(aps.ap_another1.position,an='ac1_p')
test.test(an='ac3')
test.test(an='ac4')
test.test_position(aps.ap_another2.position,an='ac2_p')
test.test(an='ac5')
test.test(an='ac6')
test.test_position(aps.ap_another3.position,an='ac3_p')"""
    )

    evaluate_nodes(
        project2.action_points[0], node, {}, c_s, project2, {"test": Test}, [ap_another1, ap_another2, ap_another3]
    )

    project2.action_points[0].actions[0].name = "ac1"
    project2.action_points[0].actions[1].name = "ac4"
    project2.action_points[0].actions[2].name = "ac1_p"
    project2.action_points[1].actions[0].name = "ac2"
    project2.action_points[1].actions[1].name = "ac2_p"
    project2.action_points[1].actions[2].name = "ac5"
    project2.action_points[2].actions[0].name = "ac3"
    project2.action_points[2].actions[1].name = "ac6"
    project2.action_points[2].actions[2].name = "ac3_p"


@pytest.mark.xfail()
def test_evaluate_nodes2() -> None:
    # "if" after "if and elif" without method between
    project2 = Project("p1", "s1")
    ap_another = ActionPoint("ap_another", Position())
    project2.action_points.append(ap_another)

    ac1 = Action("ac1", f"{next(c_s.objects).id}/test", flows=[Flow(outputs=["bool_res1"])])
    ap1.actions.append(ac1)

    project2.logic.append(LogicItem(LogicItem.START, ac1.id))
    project2.logic.append(LogicItem(ac1.id, ""))

    node = ast.parse(
        """
if bool_res1 == True:
    test.test(an='ac2')
elif bool_res1 == False:
    test.test(an='ac3')
if bool_res2 == True:
    test.test(an='ac2')
elif bool_res2 == False:
    test.test(an='ac3')"""
    )

    evaluate_nodes(ap1, node, {"bool_res1": "id123", "bool_res2": "id456"}, c_s, project2, {"test": Test}, [])


def test_evaluate_nodes3() -> None:
    # unsupported operation
    project2 = Project("p1", "s1")
    ap_another = ActionPoint("ap_another", Position())
    project2.action_points.append(ap_another)

    ac1 = Action("ac1", f"{next(c_s.objects).id}/test", flows=[Flow(outputs=["bool_res1"])])
    ap1.actions.append(ac1)

    project2.logic.append(LogicItem(LogicItem.START, ac1.id))
    project2.logic.append(LogicItem(ac1.id, ""))

    node = ast.parse(
        """def function():
    pass"""
    )

    try:
        evaluate_nodes(ap1, node, {"bool_res1": "id123", "bool_res2": "id456"}, c_s, project2, {"test": Test}, [])
        AssertionError()
    except Arcor2Exception:
        assert True


def test_evaluate_nodes4() -> None:
    # unsupported expression
    project2 = Project("p1", "s1")
    ap_another = ActionPoint("ap_another", Position())
    project2.action_points.append(ap_another)

    node = ast.parse("1 + 2")

    try:
        evaluate_nodes(ap1, node, {}, c_s, project2, {"test": Test}, [])
        AssertionError()
    except Arcor2Exception:
        assert True


def test_evaluate_nodes5() -> None:
    # unsupported assign
    project2 = Project("p1", "s1")
    ap_another = ActionPoint("ap_another", Position())
    project2.action_points.append(ap_another)

    node = ast.parse("variable = 1 + 2")

    try:
        evaluate_nodes(ap1, node, {}, c_s, project2, {"test": Test}, [])
        AssertionError()
    except Arcor2Exception:
        assert True


def test_evaluate_nodes6() -> None:
    # using function
    project2 = Project("p1", "s1")
    ap_another = ActionPoint("ap_another", Position())
    project2.action_points.append(ap_another)

    node = ast.parse('print("hello")')

    try:
        evaluate_nodes(ap1, node, {}, c_s, project2, {"test": Test}, [])
        AssertionError()
    except Arcor2Exception:
        assert True
