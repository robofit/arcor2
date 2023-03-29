import ast
import inspect
import json
from ast import Assign, Expr, If

from arcor2.cached import CachedProject
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
    gen_actions,
    gen_logic,
    gen_logic_after_if,
    gen_logic_for_if,
    get_object_by_name,
    get_parameters,
)
from arcor2_build.source.utils import find_Call


class Test_class(StrEnum):

    CLASS1: str = "1"
    CLASS2: str = "2"


class Test(Generic):

    INT = 1234

    def get_int(self, an: None | str = None) -> int:
        return self.INT

    def test(self, an: None | str = None) -> bool:
        return True

    def test_par(self, param: int, an: None | str = None) -> None:
        pass

    def test_pose(self, param: Pose, an: None | str = None) -> None:
        pass

    def test_joints(self, param: ProjectRobotJoints, an: None | str = None) -> None:
        pass

    def tests_class_value(self, param: Test_class, an: None | str = None):
        pass

    def test_all(
        self,
        param: Test_class,
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
    id_method1 = get_object_by_name("test.test", scene)
    assert id_method1 == f"{scene.objects[0].id}/test"


def test_get_object_by_name2() -> None:

    # usual case
    id_method2 = get_object_by_name("test.test_pose", scene)
    assert id_method2 == f"{scene.objects[0].id}/test_pose"


def test_get_object_by_name3() -> None:

    # nonexistent object
    try:
        get_object_by_name("nonexistent_object_.method", scene)
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

    # class value
    ap_another = ActionPoint("another", Position())
    call_node = find_Call(ast.parse('test.tests_class_value(Test_class.CLASS2,an="ac1")'))
    method = inspect.getfullargspec(Test.tests_class_value)
    parmeters, ap = get_parameters(call_node, {}, project, ap_another, method)
    StrEnum_type = plugin_from_type(StrEnum)

    assert parmeters[0] == ActionParameter("param", StrEnum_type.type_name(), json.dumps(Test_class.CLASS2))
    assert ap == ap_another


def test_get_parameters7() -> None:

    # all parameter types
    ap_another = ActionPoint("another", Position())
    StrEnum_type = plugin_from_type(StrEnum)
    joints_type = plugin_from_type(ProjectRobotJoints)
    pose_type = plugin_from_type(Pose)

    call_node = find_Call(
        ast.parse(
            """test.test_all(Test_class.CLASS1, aps.ap1.joints.default, aps.ap1.poses.default, variable, 42,
            int_const, an="ac1")"""
        )
    )
    method = inspect.getfullargspec(Test.test_all)
    parmeters, ap = get_parameters(call_node, {"variable": "id123"}, project, ap_another, method)

    assert parmeters[0] == ActionParameter("param", StrEnum_type.type_name(), json.dumps(Test_class.CLASS1))
    assert parmeters[1] == ActionParameter("joint", joints_type.type_name(), json.dumps(ap1.robot_joints[0].id))
    assert parmeters[2] == ActionParameter("pose", pose_type.type_name(), json.dumps(ap1.orientations[0].id))
    assert parmeters[3] == ActionParameter("int_param1", ActionParameter.TypeEnum.LINK, json.dumps("id123/default/0"))
    assert parmeters[4] == ActionParameter("int_param2", plugin_from_type(type(42)).type_name(), json.dumps(42))
    assert parmeters[5] == ActionParameter(
        "int_param3", ActionParameter.TypeEnum.PROJECT_PARAMETER, json.dumps(const.id)
    )
    assert ap == ap1


# TODO: wrong number of parameters


def test_gen_actions1() -> None:

    # basic case
    tree = ast.parse('test.test(an="ac1")')
    if isinstance(tree.body[0], Expr):
        node = tree.body[0]

    _ac1, variables, action_point = gen_actions(
        ActionPoint("ap", Position()), node, {}, scene, project, {"test": Test}, ""
    )
    assert action_point.actions[0].name == "ac1"
    assert action_point.actions[0].type == f"{scene.objects[0].id}/test"
    assert action_point.actions[0].parameters == []
    assert action_point.actions[0].flows == [Flow()]
    assert variables == {}


def test_gen_actions2() -> None:

    # case whit output
    tree = ast.parse('variable = test.test(an="ac1")')

    print(ast.dump(tree, indent=4))

    if isinstance(tree.body[0], Assign):
        node = tree.body[0]

    ac1, variables, action_point = gen_actions(
        ActionPoint("ap", Position()), node, {}, scene, project, {"test": Test}, "variable"
    )
    assert action_point.actions[0].name == "ac1"
    assert action_point.actions[0].type == f"{scene.objects[0].id}/test"
    assert action_point.actions[0].parameters == []
    assert action_point.actions[0].flows == [Flow(outputs=["variable"])]
    assert variables == {"variable": ac1}


def test_gen_actions3() -> None:

    # case whit parameter
    tree = ast.parse('variable = test.test_par(variable,an="ac1")')
    if isinstance(tree.body[0], Assign):
        node = tree.body[0]

    _ac1, variables, action_point = gen_actions(
        ActionPoint("ap", Position()), node, {"variable": "id123"}, scene, project, {"test": Test}, ""
    )
    assert action_point.actions[0].name == "ac1"
    assert action_point.actions[0].type == f"{scene.objects[0].id}/test_par"
    assert action_point.actions[0].parameters == [
        ActionParameter("param", ActionParameter.TypeEnum.LINK, json.dumps("id123/default/0"))
    ]
    assert action_point.actions[0].flows == [Flow()]
    assert variables == {"variable": "id123"}


def test_gen_actions4() -> None:

    # nonexistent method
    tree = ast.parse('test.nothing(an="ac1")')
    if isinstance(tree.body[0], Expr):
        node = tree.body[0]

    try:
        gen_actions(ActionPoint("ap", Position()), node, {}, scene, project, {"test": Test}, "")
        AssertionError()
    except Arcor2Exception:
        assert True


def test_evaluate_if1() -> None:

    # usual case
    project2 = Project("p1", "s1")
    ap_another = ActionPoint("ap_another", Position())
    project2.action_points.append(ap_another)

    ac1 = Action("ac1", f"{scene.objects[0].id}/test", flows=[Flow(outputs=["bool_res1"])])
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
        ap_another, node, {"bool_res1": "id123", "bool_res2": "id456"}, ac1.id, scene, project2, {"test": Test}
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

    # "if" in "if" without method between
    project2 = Project("p1", "s1")
    ap_another = ActionPoint("ap_another", Position())
    project2.action_points.append(ap_another)

    ac1 = Action("ac1", f"{scene.objects[0].id}/test", flows=[Flow(outputs=["bool_res1"])])
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
        evaluate_if(ap1, node, {"bool_res1": "id123", "bool_res2": "id456"}, ac1.id, scene, project2, {"test": Test})
        AssertionError()
    except Arcor2Exception:
        assert True


def test_evaluate_if3() -> None:

    # more conditions in "if"
    project2 = Project("p1", "s1")
    ap_another = ActionPoint("ap_another", Position())
    project2.action_points.append(ap_another)

    ac1 = Action("ac1", f"{scene.objects[0].id}/test", flows=[Flow(outputs=["bool_res1"])])
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
        evaluate_if(ap1, node, {"bool_res1": "id123", "bool_res2": "id456"}, ac1.id, scene, project2, {"test": Test})
        AssertionError()
    except Arcor2Exception:
        assert True


def test_evaluate_if4() -> None:

    # condition is value
    project2 = Project("p1", "s1")
    ap_another = ActionPoint("ap_another", Position())
    project2.action_points.append(ap_another)

    ac1 = Action("ac1", f"{scene.objects[0].id}/test", flows=[Flow(outputs=["bool_res1"])])
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
        evaluate_if(ap1, node, {"bool_res1": "id123"}, ac1.id, scene, project2, {"test": Test})
        AssertionError()
    except Arcor2Exception:
        assert True


def test_evaluate_if5() -> None:

    # nonexistent variable
    project2 = Project("p1", "s1")
    ap_another = ActionPoint("ap_another", Position())
    project2.action_points.append(ap_another)

    ac1 = Action("ac1", f"{scene.objects[0].id}/test", flows=[Flow(outputs=["bool_res1"])])
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
        evaluate_if(ap1, node, {"bool_res1": "id123"}, ac1.id, scene, project2, {"test": Test})
        AssertionError()
    except Arcor2Exception:
        assert True


def test_evaluate_if6() -> None:

    # condition is method
    project2 = Project("p1", "s1")
    ap_another = ActionPoint("ap_another", Position())
    project2.action_points.append(ap_another)

    ac1 = Action("ac1", f"{scene.objects[0].id}/test", flows=[Flow(outputs=["bool_res1"])])
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
        evaluate_if(ap1, node, {"bool_res1": "id123"}, ac1.id, scene, project2, {"test": Test})
        AssertionError()
    except Arcor2Exception:
        assert True


# TODO: only "if"


def test_evaluate_nodes1() -> None:
    # TODO: shoud this work?

    # "if" after "if and elif" without method between
    project2 = Project("p1", "s1")
    ap_another = ActionPoint("ap_another", Position())
    project2.action_points.append(ap_another)

    ac1 = Action("ac1", f"{scene.objects[0].id}/test", flows=[Flow(outputs=["bool_res1"])])
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

    try:
        evaluate_nodes(ap1, node, {"bool_res1": "id123", "bool_res2": "id456"}, scene, project2, {"test": Test})
        AssertionError()
    except Arcor2Exception:
        assert True


def test_evaluate_nodes2() -> None:

    # unsaported operation
    project2 = Project("p1", "s1")
    ap_another = ActionPoint("ap_another", Position())
    project2.action_points.append(ap_another)

    ac1 = Action("ac1", f"{scene.objects[0].id}/test", flows=[Flow(outputs=["bool_res1"])])
    ap1.actions.append(ac1)

    project2.logic.append(LogicItem(LogicItem.START, ac1.id))
    project2.logic.append(LogicItem(ac1.id, ""))

    node = ast.parse(
        """
test.test(an='ac1')
def function():
    pass"""
    )

    try:
        evaluate_nodes(ap1, node, {"bool_res1": "id123", "bool_res2": "id456"}, scene, project2, {"test": Test})
        AssertionError()
    except Arcor2Exception:
        assert True


# TODO: wrong Expr and Assign
