import ast
import inspect
import json
from ast import Assign, Attribute, Call, Compare, Constant, Continue, Expr, If, Module, Name, While
from copy import deepcopy

from arcor2.cached import CachedScene
from arcor2.data.common import (
    Action,
    ActionParameter,
    ActionPoint,
    Flow,
    FlowTypes,
    LogicItem,
    Pose,
    Position,
    Project,
    ProjectLogicIf,
    ProjectRobotJoints,
    Scene,
)
from arcor2.exceptions import Arcor2Exception
from arcor2.object_types.abstract import Generic
from arcor2.parameter_plugins.utils import plugin_from_type
from arcor2_build.source.utils import SpecialValues, find_Call, find_Compare, find_While


def action_point_in_list(action_points: list[ActionPoint], action_name: str) -> str | None:
    """return id of action_point from list[ActionPoint] where sent action_name
    is name of action which is in this action_point.

    :param action_points: List of action_points that is analyzed
    :param action_name:   Name of action which is looked for

    :return:        Id of action_point
    """
    for action_point in action_points:
        for action in action_point.actions:
            if action.name == action_name:
                return action_point.id
    return None


def get_parameters(
    rest_of_node: Call,
    variables: dict[str, str],
    project: Project,
    action_point: ActionPoint,
    method: inspect.FullArgSpec,
) -> tuple[list[ActionParameter], ActionPoint]:
    """returns list of parametres for action that is in rest_of_node.

    :param rest_of_node:  Part of tree that is analyzed.
    :param variables:     Dict keeping result of actions ['variable':'ac_id', 'variable':'ac_id', ...].
    :param project:       Project where are stored project parameters
    :param action_point:  Last seen action_point where a new action will be added.
    :param method:        information about called method

    :return list[ActionParameter]:  List of generated paramters from method.
    :return ActionPoint:            Last seen action_point.
    """

    parameters: list[ActionParameter] = []
    # -2 because in AST "self" and "an" parameter is not in args
    # if in parameters of method is before "an" * then "an" is not in method.args
    if len(rest_of_node.args) != len(method.args) - 2 + len(method.kwonlyargs):
        raise Arcor2Exception(f"Wrong number of parameters in method {ast.unparse(rest_of_node)}")

    for i in range(len(rest_of_node.args)):
        param_name = method.args[i + 1]  # +1 to skip self parameter
        param_type = ""
        param_value = ""

        arg = rest_of_node.args[i]
        if isinstance(arg, Constant):  # constant
            value_type = plugin_from_type(method.annotations[param_name])

            if plugin_from_type(type(arg.value)) != value_type:
                raise Arcor2Exception(f"Value {arg.value} type in method is not equal to the required value type")

            param_type = value_type.type_name()
            param_value = value_type.value_to_json(arg.value)

        elif isinstance(arg, Attribute):  # class... it can be action_point
            str_arg = ast.unparse(arg)
            if not ("aps." in str_arg) and isinstance(arg.value, Name):  # class value
                value_type = plugin_from_type(method.annotations[param_name])
                param_type = value_type.type_name()

                try:
                    value = (getattr(method.annotations[param_name], arg.attr)).value  # get value from atribute
                    param_value = value_type.value_to_json(value)
                except AttributeError:
                    str_arg = ast.unparse(arg)
                    dot_position = str_arg.find(".")
                    raise Arcor2Exception(f"Class {str_arg[:dot_position]} has not attribute {arg.attr}")

            else:  # action_point value
                for ap in project.action_points:
                    if (
                        isinstance(arg, Attribute)
                        and isinstance(arg.value, Attribute)
                        and isinstance(arg.value.value, Attribute)
                    ):
                        if ap.name == arg.value.value.attr:  # find action_point
                            action_point = ap
                            if arg.value.attr == SpecialValues.poses:  # actiopn_point.orientations "poses"
                                for pose in ap.orientations:
                                    if pose.name == arg.attr:
                                        param_value = json.dumps(pose.id)
                                        param_type = plugin_from_type(Pose).type_name()

                            elif arg.value.attr == SpecialValues.joints:  # action_point.robot_joints "joints"
                                for joint in ap.robot_joints:
                                    if joint.name == arg.attr:
                                        param_value = json.dumps(joint.id)
                                        param_type = plugin_from_type(ProjectRobotJoints).type_name()

                    elif isinstance(arg, Attribute) and isinstance(arg.value, Attribute):
                        if ap.name == arg.value.attr:  # action_point as parameter
                            action_point = ap
                            param_value = json.dumps(ap.id)
                            param_type = plugin_from_type(Position).type_name()

                if not param_value:
                    raise Arcor2Exception(f"ActionPoint {str_arg} was not found")
                if plugin_from_type(method.annotations[param_name]).type_name() != param_type:
                    raise Arcor2Exception(
                        f"Value {ast.unparse(arg)} type in method is not equal to the required value type"
                    )

        elif isinstance(arg, Name):  # variable defined in script or variable from project parameters
            arg_name = ast.unparse(arg)
            if arg_name in variables:
                param_type = ActionParameter.TypeEnum.LINK
                param_value = json.dumps(f"{variables[arg_name]}/default/0")
            else:
                for param in project.parameters:
                    if arg.id == param.name:
                        param_type = ActionParameter.TypeEnum.PROJECT_PARAMETER
                        param_value = json.dumps(param.id)
                        break
            if not (param_type or param_value):
                raise Arcor2Exception(f"Variable {arg_name} was not found")
        else:
            raise Arcor2Exception(f"Unsupported operation in {ast.unparse(rest_of_node)}")
        parameters.append(ActionParameter(param_name, param_type, param_value))

    return parameters, action_point


def gen_action(
    action_point: ActionPoint,
    rest_of_node: Call,
    variables: dict[str, str],
    scene: CachedScene,
    project: Project,
    object_type: dict[str, type[Generic]],
    flows: list[str],
    action_points: list[ActionPoint],  # list of action_points from original project
) -> tuple[str, dict, ActionPoint]:
    """Generate action from node dependencies.

    :param action_point:  Last seen action_point where a new action will be added.
    :param rest_of_node:  Part of tree that is analyzed.
    :param variables:     Dict keeping result of actions ['variable':'ac_id', 'variable':'ac_id', ...].
    :param scene:         CachedScene contains objects id
    :param project:       Project where will be added new action
    :param object_type:   Dict of objects used in program
    :param flows:         Flows for action.
    :param action_points: List of action_points from original project.

    :return str:            Id of generated action.
    :return dict:           Updated varibales.
    :return ActionPoint:    Last seen action_point.
    """

    # name
    name = ""
    try:
        for key in rest_of_node.keywords:
            if "an" == key.arg and isinstance(key.value, Constant):
                name = key.value.value
        if not name:
            raise AttributeError
    except AttributeError:
        raise Arcor2Exception(f'Missing value "an" in {ast.unparse(rest_of_node)}')

    if action_point_in_list(project.action_points, name):
        raise Arcor2Exception(f"Name {name} of action is already used")

    # find action_point where shoud by added new action
    action_point_id = action_point_in_list(action_points, name)
    if action_point_id:
        tmp = project.find_action_point(action_point_id)
        if tmp:  # if action_point was not found, last seen action point will be not overwritten
            action_point = tmp

    # type
    object_method = ast.unparse(rest_of_node.func)
    scene_object = scene.get_object_by_name(object_method)

    # parameters
    dot_position = object_method.find(".")  # split object.method() to object and method
    object_name = object_method[:dot_position]
    method_name = object_method[dot_position + 1 :]

    try:
        tmp = getattr(object_type[object_name], method_name)
    except AttributeError:
        raise Arcor2Exception(f"Method {method_name} does not exist")

    method = inspect.getfullargspec(tmp)  # get infomation about method
    parameters, action_point = get_parameters(rest_of_node, variables, project, action_point, method)
    # action_point -> action will be added to action_point that was used as parameter

    # flows
    final_flows: list[Flow] = []
    if flows:
        for flow in flows:
            final_flows.append(Flow(outputs=[(flow)]))
    else:
        final_flows = [Flow()]

    # create action
    ac1 = Action(name, scene_object, flows=final_flows, parameters=parameters)
    action_point.actions.append(ac1)  # add actions to last seen action_point

    # if variable was declared, it will be added to dict with action id ['name':'id', 'name':'id', ...]
    if flows != "":
        for flow in flows:
            variables[flow] = ac1.id

    return ac1.id, variables, action_point


def gen_logic(ac_id: str, logic_list: list[LogicItem]) -> None:
    """add end point as ac_id to the last LogicItem and generate new LogicItem
    with "start" in ac_id.

    :param ac_id:         Id of action that should be used
    :param logic_list:    List of LogicItems that shoud be modified
    """

    logic_list[-1].end = ac_id
    item = LogicItem(ac_id, "")
    logic_list.append(item)
    return


def gen_logic_for_if(ac_id: str, logic_list: list[LogicItem]) -> None:
    """generate new LogicItem with "start" in ac_id.

    :param ac_id:         Id of action that should be used
    :param logic_list:    List of LogicItems that shoud be modified
    """

    item = LogicItem(ac_id, "")
    logic_list.append(item)
    return


def gen_logic_after_if(ac_id: str, logic_list: list[LogicItem]) -> None:
    """looking for empty "end" in logic_list and adding ac_id. At the end
    generate one more LogicItem with "start" in ac_id.

    :param ac_id:         Id of action that should be used
    :param logic_list:    List of LogicItems that shoud be modified
    """

    for logic_item in logic_list:
        if logic_item.end == "":
            logic_item.end = ac_id
    item = LogicItem(ac_id, "")
    logic_list.append(item)
    return


def evaluate_if(
    action_point: ActionPoint,
    node: If,
    variables: dict[str, str],
    ac_id: str,
    scene: CachedScene,
    project: Project,
    object_type: dict[str, type[Generic]],
    action_points: list[ActionPoint],
) -> dict:
    """generate Actions and logicItems for conditions from node into the
    project.

    :paramaction_point:  Last seen action_point where a new action will be added.
    :param node:          Part of tree that is analyzed.
    :param variables:     Dict keeping result of actions ['variable':'ac_id', 'variable':'ac_id', ...].
    :param ac_id:         Id of action that was before condition.
    :param scene:         CachedScene contains objects id .
    :param project:       Project where will be added new actions.
    :param object_type:   Dict of objects used in program.
    :param action_points: List of action_points from original project.

    :return:        Updated variables.
    """

    if not isinstance(node.test, Compare):
        raise Arcor2Exception('Condition must be in this form: if "variable" == "value":')
    rest_of_node = find_Compare(node)

    what_name = ast.unparse(rest_of_node.left)
    try:
        what = variables[what_name] + "/" + FlowTypes.DEFAULT + "/0"
    except KeyError:
        raise Arcor2Exception(f"Variable {what_name} does not exist")

    try:
        # take type from condition and transforom it into arcor2 type
        value_type = plugin_from_type(type(rest_of_node.comparators[0].value))
        value = value_type.value_to_json(rest_of_node.comparators[0].value)
    except KeyError:
        raise Arcor2Exception(f"Unsupported operation in {ast.unparse(node)}")

    if ac_id:  # node "elif"
        gen_logic_for_if(ac_id, project.logic)

    else:  # node first "if"
        ac_id = project.logic[-1].start

    if isinstance(node.body[0], If):
        raise Arcor2Exception('After "if" can not be another "if" without method between')

    project.logic[-1].condition = ProjectLogicIf(f"{what}", value)
    variables = evaluate_nodes(action_point, node, variables, scene, project, object_type, action_points)

    if node.orelse:
        # if "if" or "elif" is followed by "else" or "elif" this will find and evaluate all of them
        for else_or_if_node in node.orelse:
            if isinstance(else_or_if_node, If):
                variables = evaluate_if(
                    action_point, else_or_if_node, variables, ac_id, scene, project, object_type, action_points
                )

    return variables


def evaluate_nodes(
    action_point: ActionPoint,
    tree: If | While | Module,
    variables: dict[str, str],
    scene: CachedScene,
    project: Project,
    object_type: dict[str, type[Generic]],
    action_points: list[ActionPoint],  # list of action_points from original project
) -> dict:
    """function iterates through sent tree and generates LogicItems and Actions
    into the sent project.

    :param action_point:  Last seen action_point where a new action will be added.
    :param tree:          Tree from script that is analyzed
    :param variables:     Dict keeping result of actions ['variable':'ac_id', 'variable':'ac_id', ...].
    :param scene:         CachedScene contains objects id .
    :param project:       Project where will be added new Actions and LogicItems.
    :param object_type:   Dict of objects used in program.
    :param action_points: List of action_points from original project.

    :return:        Updated variables.
    """

    # True: for generating Logicitem will be used gen_logic_after_if()
    # False: for generating Logicitem will be used gen_logic()
    after_if = False

    ac_id = ""  # id of last generated action

    for node in tree.body:
        if isinstance(node, Expr) or isinstance(node, Assign):
            try:
                rest_of_node = find_Call(node)
            except AttributeError:
                raise Arcor2Exception(f"Unsupported command {ast.unparse(node)}")

            flows = []
            if isinstance(node, Assign):
                for flow in node.targets:
                    flows.append(ast.unparse(flow))

            ac_id, variables, action_point = gen_action(
                action_point, rest_of_node, variables, scene, project, object_type, flows, action_points
            )

            if after_if:
                gen_logic_after_if(ac_id, project.logic)
                after_if = False
            else:
                gen_logic(ac_id, project.logic)

        elif isinstance(node, If):
            if after_if:
                raise Arcor2Exception('After "if or elif" cannot be another "if" witout method between them)')
            else:
                ac_id = project.logic[-1].start
                variables = evaluate_if(action_point, node, variables, "", scene, project, object_type, action_points)
                after_if = True

        elif isinstance(node, Continue):
            project.logic[-1].end = LogicItem.END
            break

        else:
            raise Arcor2Exception(f"Unsupported operation {ast.unparse(node)}")
    return variables


def python_to_json(project: Project, scene: Scene, script: str, object_type: dict[str, type[Generic]]) -> Project:
    """compile Python code into the JSON data that is saved in the project.

    :param project:       Project where will be added new Actions and LogicItems.
    :param scene:         Scene contains objects id.
    :param script:        Script which have to be compiled.
    :param object_type:   Dict of objects used in program.

    :return:        Compiled script in project
    """

    # dict keeping result of actions ['variable':'ac_id', 'variable':'ac_id', ...]
    variables: dict[str, str] = {}

    try:
        tree = ast.parse(script)
    except SyntaxError:
        raise Arcor2Exception("Script contains syntax error")
    try:
        while_node = find_While(tree)
    except AttributeError:
        raise Arcor2Exception('Missing "while" in script')

    action_points = deepcopy(project.action_points)

    # cleaning project
    for action_point in project.action_points:
        action_point.actions = []
    project.logic = []
    project.logic.append(LogicItem(LogicItem.START, LogicItem.END))

    evaluate_nodes(
        project.action_points[0], while_node, variables, CachedScene(scene), project, object_type, action_points
    )

    # adding END into LogicItem with empty "end"
    for logic_item in project.logic:
        if logic_item.end == "":
            logic_item.end = LogicItem.END

    return project
