import ast
import inspect
import json
import logging
import os
import sys
import tempfile
import zipfile
from ast import Assign, Attribute, Call, Compare, Constant, Continue, Expr, If, Module, Name, While

import humps

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
from arcor2.data.object_type import ObjectType
from arcor2.exceptions import Arcor2Exception
from arcor2.helpers import save_and_import_type_def
from arcor2.logging import get_logger
from arcor2.object_types.abstract import Generic
from arcor2.object_types.utils import prepare_object_types_dir
from arcor2.parameter_plugins.utils import plugin_from_type
from arcor2.source.utils import parse as Parse
from arcor2_build.scripts.build import get_base_from_imported_package, read_dc_from_zip, read_str_from_zip
from arcor2_build.source.utils import find_Call, find_Compare, find_keyword, find_While
from arcor2_build_data.exceptions import InvalidPackage, NotFound

logger = get_logger(__name__, logging.DEBUG if env.get_bool("ARCOR2_LOGIC_DEBUG", False) else logging.INFO)

# https://github.com/robofit/arcor2/blob/master/src/python/arcor2_build/source/utils.py#L394.
POSES = "poses"  # TODO: place arcor2_build/source/__init__.py
JOINTS = "joints"


# debug function
def action_print(project: Project):
    count = 1
    for k in range(len(project.action_points)):
        print("||-----------||" + project.action_points[k].name + "||------------||")
        print()
        for i in project.action_points[k].actions:
            print("----------------Action", end="")
            print(count, end="")
            print("-----------------")
            print("Name:\t" + i.name)
            print("Type:\t" + i.type)
            print("Id:\t" + i.id)
            print("Param:\t")
            for j in i.parameters:
                print("\t", end="")
                print(j)
            print("Flows:\t")
            for o in i.flows:
                print("\t", end="")
                print(o)
            print()
            count += 1


# debug function
def logic_print(project: Project):
    count = 1
    for i in project.logic:
        print("----------------Logic", end="")
        print(count, end="")
        print("-----------------")
        print("Start:\t" + i.start)
        print("End:\t" + i.end)
        print("Con:\t", end="")
        print(i.condition)
        print("Id:\t" + i.id)
        print()
        count += 1


def zip_package(folder: str):  # TODO: place somewhere else

    zf = zipfile.ZipFile(folder + ".zip", "w")
    for dirname, _subdirs, files in os.walk(folder):
        for filename in files:
            if dirname.find(folder + "/") != -1:
                zf.write(os.path.join(dirname, filename), dirname.replace(folder + "/", "") + "/" + filename)
            else:
                zf.write(os.path.join(dirname, filename), filename)
    return zf


def get_pro_sce_scr(zip_file):  # TODO: remove?
    OBJECT_TYPE_MODULE = "arcor2_object_types"
    original_sys_path = list(sys.path)
    original_sys_modules = dict(sys.modules)

    project: Project
    scene: Scene
    script = None
    objects: dict[str, ObjectType] = {}
    object_type: dict[str, type[Generic]] = {}

    try:
        project = read_dc_from_zip(zip_file, "data/project.json", Project)
    except KeyError:
        raise NotFound("Could not find project.json.")

    try:
        scene = read_dc_from_zip(zip_file, "data/scene.json", Scene)
    except KeyError:
        raise NotFound("Could not find scene.json.")

    with tempfile.TemporaryDirectory() as tmp_dir:

        # restore original environment
        sys.path = list(original_sys_path)
        sys.modules = dict(original_sys_modules)

        prepare_object_types_dir(tmp_dir, OBJECT_TYPE_MODULE)

        for scene_obj in scene.objects:
            obj_type_name = scene_obj.type

            if obj_type_name in objects:  # there might be more instances of the same type
                continue
            logger.debug(f"Importing {obj_type_name}.")

            obj_type_src = ""
            try:
                obj_type_src = read_str_from_zip(zip_file, f"object_types/{humps.depascalize(obj_type_name)}.py")
            except KeyError:
                raise NotFound(f"Object type {obj_type_name} is missing in the package.")

            try:
                ast = Parse(obj_type_src)
            except Arcor2Exception:
                raise InvalidPackage(f"Invalid code of the {obj_type_name} object type.")

            # TODO fill in OT description (is it used somewhere?)
            objects[obj_type_name] = ObjectType(obj_type_name, obj_type_src)
            get_base_from_imported_package(objects[obj_type_name], objects, zip_file, tmp_dir, ast)
            type_def = save_and_import_type_def(obj_type_src, obj_type_name, Generic, tmp_dir, OBJECT_TYPE_MODULE)

            object_type[scene_obj.name] = type_def

            assert obj_type_name == type_def.__name__
            if type_def.abstract():
                raise InvalidPackage(f"Scene contains abstract object type: {obj_type_name}.")

    try:
        script = zip_file.read("script.py").decode("UTF-8")
    except KeyError:
        raise NotFound("Could not find script.py.")

    return project, scene, script, object_type


def get_parameters(
    rest_of_node: Call, variables: dict, project: Project, action_point: ActionPoint, method: inspect.FullArgSpec
):
    # TODO: chceck num of parameters
    parameters = []
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
            if str_arg.find("aps.") == -1 and isinstance(arg.value, Name):  # class value
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
            if param_type == "" and param_value == "":
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
    node: Expr | Assign,
    variables: dict,
    scene: Scene,
    project: Project,
    object_type: dict,
    flows: str = "",
):
    rest_of_node = find_Call(node)
    parameters = []

    # flows
    final_flows = [Flow()]
    if flows:
        final_flows = [Flow(outputs=[(flows)])]

    # name
    name = ast.unparse(find_keyword(rest_of_node).value).replace("'", "")

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
        raise Arcor2Exception('Condition must by in from: if "Variable" == "Value":')
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

        if isinstance(node, Expr):
            # TODO: difrent expr -> err
            ac_id, variables, action_point = gen_actions(action_point, node, variables, scene, project, object_type)

            if condition:
                gen_logic_after_if(ac_id, project.logic)
                condition = False
            else:
                gen_logic(ac_id, project.logic)

        elif isinstance(node, Assign):
            flows = ast.unparse(node.targets[0])
            # TODO: difrent assign -> err

            if len(node.targets) > 1:
                raise Arcor2Exception("Method can have only one output")

            ac_id, variables, action_point = gen_actions(
                action_point, node, variables, scene, project, object_type, flows
            )

            if condition:
                gen_logic_after_if(ac_id, project.logic)
                condition = False
            else:
                gen_logic(ac_id, project.logic)

        elif isinstance(node, If):
            if condition:
                raise Arcor2Exception('After "elif" cannot be another "if" witout method between them)')
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

    ########################################
    # cleaning project
    for action_points in project.action_points:
        action_points.actions = []
    project.logic = []
    start_item = LogicItem(LogicItem.START, "")
    project.logic.append(start_item)
    ########################################

    evaluate_nodes(project.action_points[0], while_node, variables, scene, project, object_type)

    # adding END in to LogicItem with empty end
    for logic_item in project.logic:
        if logic_item.end == "":
            logic_item.end = LogicItem.END

    return project


def between_step(zip_file) -> Project:
    """function just connecting reading information from execution package and
    compiler."""

    original_project, scene, script, object_type = get_pro_sce_scr(zip_file)

    # action_print(original_project)

    modified_project = python_to_json(original_project, scene, script, object_type)

    # action_print(modified_project)

    return modified_project
