import ast
import inspect
import json
import logging
from ast import Assign, Attribute, Call, Compare, Constant, Continue, Expr, If, Module, Name, While

from arcor2 import env
from arcor2.data.common import (
    Action,
    ActionParameter,
    ActionPoint,
    Flow,
    FlowTypes,
    LogicItem,
    Project,
    ProjectLogicIf,
    Scene,
)
from arcor2.exceptions import Arcor2Exception
from arcor2.logging import get_logger
from arcor2.parameter_plugins.utils import plugin_from_type
from arcor2_build.source.utils import find_Call, find_Compare, find_keyword, find_While

# https://github.com/robofit/arcor2/blob/master/src/python/arcor2_build/source/utils.py#L394.
POSES = "poses"  # TODO: place arcor2_build/source/__init__.py
JOINTS = "joints"

logger = get_logger(__name__, logging.DEBUG if env.get_bool("ARCOR2_LOGIC_DEBUG", False) else logging.INFO)


def get_parameters(
    rest_of_node: Call, variables: dict, project: Project, action_point: ActionPoint, method: inspect.FullArgSpec
):
    parameters = []

    # TODO: check small number of parameters
    if len(rest_of_node.args) > len(method.args) - 1:  # -1 because in AST "slef" parameter is not in args
        raise Arcor2Exception(f"Wrong number of parameters in method {method}")

    for i in range(len(rest_of_node.args)):
        param_name = method.args[i + 1]  # +1 to skip self parameter
        param_type = ""
        param_value = ""

        arg = rest_of_node.args[i]
        if isinstance(arg, Constant):  # constant
            value_type = plugin_from_type(method.annotations[param_name])

            if plugin_from_type(type(arg.value)) != value_type:
                raise Arcor2Exception("Value type in method is not equal required value type")

            param_type = value_type.type_name()
            param_value = value_type.value_to_json(arg.value)

        elif isinstance(arg, Attribute):  # class... it can by actionpoint
            value_type = plugin_from_type(method.annotations[param_name])
            param_type = value_type.type_name()

            str_arg = ast.unparse(arg)
            if not ("aps." in str_arg) and isinstance(arg.value, Name):  # class value
                value = (getattr(method.annotations[param_name], arg.attr)).value
                param_value = value_type.value_to_json(value)

            else:  # action_point value
                for ap in project.action_points:
                    if (
                        isinstance(arg, Attribute)
                        and isinstance(arg.value, Attribute)
                        and isinstance(arg.value.value, Attribute)
                    ):
                        if ap.name == arg.value.value.attr:
                            action_point = ap
                            if arg.value.attr == POSES:
                                param_value = json.dumps(ap.orientations[0].id)
                            elif arg.value.attr == JOINTS:
                                param_value = json.dumps(ap.robot_joints[0].id)
                            else:
                                param_value = json.dumps(ap.id)

        elif isinstance(arg, Name):  # variable definated in script or variable from project parameters
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
                raise Arcor2Exception(f"Variable {arg_name} was't found")
        else:
            raise Arcor2Exception("Unsupported operation.")
        parameters += [ActionParameter(param_name, param_type, param_value)]

    return parameters, action_point


def get_object_by_name(object_method: str, scene: Scene):  # TODO: function cachedscene
    """find object from scene by name and return object id."""

    # looking for object
    for scene_object in scene.objects:
        if object_method.find(scene_object.name + ".") != -1:
            # raplece name from code to scene definition
            object_type = object_method.replace(scene_object.name + ".", (scene_object.id + "/"))

            return object_type

    raise Arcor2Exception(f"Object {object_method} wasn't found")


def gen_actions(
    action_point: ActionPoint,
    rest_of_node: Call,
    variables: dict,
    scene: Scene,
    project: Project,
    object_type: dict,
    flows: str = "",
):
    parameters = []

    # flows
    final_flows = [Flow()]
    if flows:
        final_flows = [Flow(outputs=[(flows)])]

    # name
    try:
        name = ast.unparse(find_keyword(rest_of_node).value).replace("'", "")
    except AttributeError:
        raise Arcor2Exception(f'Missing value "an" in {ast.unparse(rest_of_node)}')

    # type
    object_method = ast.unparse(rest_of_node.func)
    scene_object = get_object_by_name(object_method, scene)

    # parameters
    dot_position = object_method.find(".")  # split object.method() to object and method
    object_name = object_method[:dot_position]
    method_name = object_method[dot_position + 1 :]

    try:
        tmp = getattr(object_type[object_name], method_name)
    except AttributeError:
        raise Arcor2Exception(f"Method {method_name} does not exists")

    method = inspect.getfullargspec(tmp)  # get infomation about method
    parameters, action_point = get_parameters(rest_of_node, variables, project, action_point, method)

    # create action
    ac1 = Action(name, scene_object, flows=final_flows, parameters=parameters)
    action_point.actions.append(ac1)  # add actions to last seen action_point

    # if variable was declared, adding it to dict with actions id ['name':'id', 'name':'id', ...]
    if flows != "":
        variables[flows] = ac1.id

    return ac1.id, variables, action_point


def gen_logic(ac_id: str, logic_list: list) -> None:
    """add logic item for common case (calling method...) logic item on last
    position get END of last ac_id and new logic item get ac_id on START."""

    logic_list[-1].end = ac_id
    item = LogicItem(ac_id, "")
    logic_list.append(item)
    return


def gen_logic_for_if(ac_id: str, logic_list: list) -> None:
    """add Logic item in case that before was "if"."""

    item = LogicItem(ac_id, "")
    logic_list.append(item)
    return


def gen_logic_after_if(ac_id: str, logic_list: list) -> None:
    """add Logic item after closing "if"(elif,else) looking for empty END and
    adding ac_id of next action."""

    for logic_item in logic_list:
        if logic_item.end == "":
            logic_item.end = ac_id
    item = LogicItem(ac_id, "")
    logic_list.append(item)
    return


def evaluate_if(
    action_point: ActionPoint, node: If, variables: dict, ac_id: str, scene: Scene, project: Project, object_type: dict
) -> dict:
    if not isinstance(node.test, Compare):
        raise Arcor2Exception('Condition must by in from: if "variable" == "value":')
    rest_of_node = find_Compare(node)

    what_name = ast.unparse(rest_of_node.left)
    try:
        what = variables[what_name] + "/" + FlowTypes.DEFAULT + "/0"  # TODO: other variables?
    except KeyError:
        raise Arcor2Exception(f"Variable {what_name} does not exist")

    try:
        # take type from condition and transforom it into arcor2 type
        value_type = plugin_from_type(type(rest_of_node.comparators[0].value))
        value = value_type.value_to_json(rest_of_node.comparators[0].value)
    except KeyError:
        raise Arcor2Exception("Unsupported operation.")

    if ac_id:  # node orelse
        gen_logic_for_if(ac_id, project.logic)

    else:  # node first if
        ac_id = project.logic[-1].start

    if isinstance(node.body[0], If):
        raise Arcor2Exception('After "if" can not be another if without method between')

    project.logic[-1].condition = ProjectLogicIf(f"{what}", value)
    variables = evaluate_nodes(action_point, node, variables, scene, project, object_type)

    if node.orelse:
        # if node orelse contains "if" or "else" and not only "elif" this will find and evaluate all of them
        for else_or_if_node in node.orelse:
            if isinstance(else_or_if_node, If):
                variables = evaluate_if(action_point, else_or_if_node, variables, ac_id, scene, project, object_type)

    return variables


def evaluate_nodes(
    action_point: ActionPoint,
    tree: If | While | Module,
    variables: dict,
    scene: Scene,
    project: Project,
    object_type: dict,
) -> dict:
    """if condition is on, then in future when should by generated new
    LogicItem, will be chcek all nodes in project.logic and added id of next
    action as end of LogicItems in case the condition is active and another
    node is "if" that node will by processed as "elif" inside "evaluate_if"."""
    condition = False
    ac_id = ""

    for node in tree.body:
        if isinstance(node, Expr) or isinstance(node, Assign):
            try:
                rest_of_node = find_Call(node)
            except AttributeError:
                raise Arcor2Exception(f"Unsuported command {ast.unparse(node)}")

            flows = ""
            if isinstance(node, Assign):
                flows = ast.unparse(node.targets[0])

            ac_id, variables, action_point = gen_actions(
                action_point, rest_of_node, variables, scene, project, object_type, flows
            )

            if condition:
                gen_logic_after_if(ac_id, project.logic)
                condition = False
            else:
                gen_logic(ac_id, project.logic)

        elif isinstance(node, If):
            if condition:
                raise Arcor2Exception('After "if or elif" cannot be another "if" witout method between them)')
                # variables = evaluate_if(action_point, node, variables, ac_id, scene, project, object_type)
            else:
                ac_id = project.logic[-1].start
                variables = evaluate_if(action_point, node, variables, "", scene, project, object_type)
                condition = True

        elif isinstance(node, Continue):
            project.logic[-1].end = LogicItem.END

        else:
            raise Arcor2Exception("Unsupported operation.")
    return variables


def python_to_json(project: Project, scene: Scene, script: str, object_type: dict) -> Project:
    # dict of variables with id actions, where variable was declared ['name':'id', 'name':'id', ...]
    variables: dict[str, str] = {}  # TODO: separate module/class within arcor2_build /function

    try:
        tree = ast.parse(script)
    except SyntaxError:
        raise Arcor2Exception("script.py contains syntax error")
    while_node = find_While(tree)

    # cleaning project
    for action_points in project.action_points:
        action_points.actions = []
    project.logic = []
    start_item = LogicItem(LogicItem.START, "")
    project.logic.append(start_item)

    evaluate_nodes(project.action_points[0], while_node, variables, scene, project, object_type)

    # adding END in to LogicItem with empty end
    for logic_item in project.logic:
        if logic_item.end == "":
            logic_item.end = LogicItem.END

    return project
