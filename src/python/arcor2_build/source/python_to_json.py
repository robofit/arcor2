import ast
import inspect
import json
import logging
import os
import sys
import tempfile
import zipfile
from ast import Assign, Attribute, Call, Constant, Continue, Expr, If, Name, While

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
from arcor2_build_data.exceptions import InvalidPackage

#######
objects: dict[str, ObjectType] = {}  # TODO: temporary solution -> will by added as parameter
object_type: dict[str, type[Generic]] = {}  # TODO: temporary solution -> will by added as parameter
######
logger = get_logger(__name__, logging.DEBUG if env.get_bool("ARCOR2_LOGIC_DEBUG", False) else logging.INFO)


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


def get_pro_sce_scr(zip_file):  # TODO: place somewhere else
    OBJECT_TYPE_MODULE = "arcor2_object_types"
    original_sys_path = list(sys.path)
    original_sys_modules = dict(sys.modules)

    project: Project
    scene: Scene
    script = None

    try:
        project = read_dc_from_zip(zip_file, "data/project.json", Project)
    except KeyError:
        print("Could not find project.json.")

    try:
        scene = read_dc_from_zip(zip_file, "data/scene.json", Scene)
    except KeyError:
        print("Could not find scene.json.")

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
                print(f"Object type {obj_type_name} is missing in the package.")

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
        print("Could not find script.py.")

    return project, scene, script


def get_parameters(rest_of_node: Call, variables: dict, file_func: str, project: Project, action_point: ActionPoint):
    parameters = []

    dot_position = file_func.find(".")  # split object.method(...) to object and method
    object = file_func[:dot_position]
    method_name = file_func[dot_position + 1 :]

    method = inspect.getfullargspec(getattr(object_type[object], method_name))  # get infomation about object

    for j in range(len(rest_of_node.args)):
        param_name = method.args[j + 1]  # +1 to skip self parameter
        param_type = ""
        param_value = ""

        arg = rest_of_node.args[j]
        if isinstance(arg, Constant):  # constant
            value_type = plugin_from_type(method.annotations[param_name])
            param_type = value_type.type_name()
            param_value = value_type.value_to_json(arg.value)

        elif isinstance(arg, Attribute):  # class... it can by actionpoint
            value_type = plugin_from_type(method.annotations[param_name])
            param_type = value_type.type_name()

            str_arg = ast.unparse(arg)
            if str_arg.find("aps.") == -1 and isinstance(arg.value, Name):  # class value

                value = (getattr(method.annotations[param_name], arg.attr)).value
                param_value = value_type.value_to_json(value)

            else:

                for ap in project.action_points:  # action_point value
                    if (
                        isinstance(arg, Attribute)
                        and isinstance(arg.value, Attribute)
                        and isinstance(arg.value.value, Attribute)
                    ):
                        if ap.name == arg.value.value.attr:
                            action_point = ap
                            if arg.value.attr == "poses":
                                param_value = json.dumps(ap.orientations[0].id)
                            elif arg.value.attr == "joints":
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
        else:
            raise Arcor2Exception("Unsupported operation.")
        parameters += [ActionParameter(param_name, param_type, param_value)]

    return parameters, action_point


def get_type(rest_of_node: Call, scene: Scene):
    file_func = ast.unparse(rest_of_node.func)
    # looking for type of action
    for object in scene.objects:
        if file_func.find(object.name + ".") != -1:
            # raplece name from code to scene definition
            type = file_func.replace(object.name + ".", (object.id + "/"))

            return type, file_func


def gen_actions(
    action_point: ActionPoint,
    node: Expr | Assign,
    variables: dict,
    scene: Scene,
    project: Project,
    flows: str = "",
):
    rest_of_node = find_Call(node)
    parameters = []

    final_flows = [Flow()]
    if flows:
        final_flows = [Flow(outputs=[(flows)])]

    name = ast.unparse(find_keyword(rest_of_node).value).replace("'", "")

    type, object_func = get_type(rest_of_node, scene)

    if rest_of_node.args != []:  # no args -> no parameters in fuction
        parameters, action_point = get_parameters(rest_of_node, variables, object_func, project, action_point)

    ac1 = Action(name, type, flows=final_flows, parameters=parameters)

    action_point.actions.append(ac1)  # add actions to last seen action_point

    # if variable was declared, adding it to dict with actions id ['name':'id', 'name':'id', ...]
    if flows != "":
        variables[flows] = ac1.id

    return ac1.id, variables, action_point


# add logic item for common case (calling function...)
# logic item on last position get END of last ac_id and
def gen_logic(ac_id: str, logic_list: list) -> None:

    logic_list[len(logic_list) - 1].end = ac_id
    item = LogicItem(ac_id, "")
    logic_list.append(item)
    return


# add Logic item in case that before was "if"
def gen_logic_for_if(ac_id: str, logic_list: list) -> None:

    item = LogicItem(ac_id, "")
    logic_list.append(item)
    return


# add Logic item after closing "if"(elif,else)
# looking for empty END and adding ac_id of next action
def gen_logic_after_if(ac_id: str, logic_list: list) -> None:
    # TODO: more ifs -> logic point from
    for i in range(len(logic_list)):
        if logic_list[i].end == "":
            logic_list[i].end = ac_id
    item = LogicItem(ac_id, "")
    logic_list.append(item)
    return


def evaluate_if(
    action_point: ActionPoint,
    logic_list: list,
    node: If,
    variables: dict,
    ac_id: str,
    scene: Scene,
    project: Project,
) -> dict:

    rest_of_node = find_Compare(node)

    what_name = ast.unparse(rest_of_node.left)
    what = variables[what_name] + "/" + FlowTypes.DEFAULT + "/0"

    try:
        # take type from condition and transforom it into arcor2 type
        value_type = plugin_from_type(type(rest_of_node.comparators[0].value))
        value = value_type.value_to_json(rest_of_node.comparators[0].value)
    except KeyError:
        raise Arcor2Exception("Unsupported operation.")

    if ac_id:  # node orelse
        gen_logic_for_if(ac_id, logic_list)

    else:  # node first if
        ac_id = logic_list[len(logic_list) - 1].start

    logic_list[len(logic_list) - 1].condition = ProjectLogicIf(f"{what}", value)
    variables = evaluate_nodes(action_point, logic_list, node, variables, scene, project)

    if node.orelse:
        # if node orelse contains "if" or "else" and not only "elif" this will find and evaluate all of them
        for else_or_if_node in node.orelse:
            if isinstance(else_or_if_node, If):
                variables = evaluate_if(action_point, logic_list, else_or_if_node, variables, ac_id, scene, project)

    return variables


def evaluate_nodes(
    action_point: ActionPoint,
    logic_list: list,
    tree: If | While,
    variables: dict,
    scene: Scene,
    project: Project,
) -> dict:

    # if condition is on, then in future when should by generated new LogicItem,
    # will be chcek all nodes in logic_list and added id of next action as end of LogicItems
    # in case the condition is active and another node is "if"
    # that node will by processed as "elif" inside "evaluate_if"
    condition = False
    ac_id = ""

    for node in tree.body:

        if isinstance(node, Expr):
            ac_id, variables, action_point = gen_actions(action_point, node, variables, scene, project)

            if condition:
                gen_logic_after_if(ac_id, logic_list)
                condition = False
            else:
                gen_logic(ac_id, logic_list)

        elif isinstance(node, Assign):
            flows = ast.unparse(node.targets[0])
            ac_id, variables, action_point = gen_actions(action_point, node, variables, scene, project, flows)

            if condition:
                gen_logic_after_if(ac_id, logic_list)
                condition = False
            else:
                gen_logic(ac_id, logic_list)

        elif isinstance(node, If):
            if condition:
                variables = evaluate_if(action_point, logic_list, node, variables, ac_id, scene, project)
            else:
                ac_id = logic_list[len(logic_list) - 1].start
                variables = evaluate_if(action_point, logic_list, node, variables, "", scene, project)
                condition = True

        elif isinstance(node, Continue):
            logic_list[len(logic_list) - 1].end = LogicItem.END

        else:
            raise Arcor2Exception("Unsupported operation.")
    return variables


def between_step(project: Project, scene: Scene, script: str):
    logic_list = list()
    start_item = LogicItem(LogicItem.START, "")
    logic_list.append(start_item)

    # dict of variables with id actions, where variable was declared ['name':'id', 'name':'id', ...]
    variables: dict[str, str] = {}  # TODO: separate module/class within arcor2_build
    tree = ast.parse(script)
    while_node = find_While(tree)

    ########################################
    for action_points in project.action_points:
        action_points.actions = []
    ########################################

    ap = project.action_points[0]
    evaluate_nodes(ap, logic_list, while_node, variables, scene, project)

    # adding END in to LogicItem with empty end
    project.logic = []
    for j in logic_list:
        if j.end == "":
            j.end = LogicItem.END

        project.logic.append(j)

    # print(variables)

    return project


def python_to_json(zip_file) -> Project:

    original_project, scene, script = get_pro_sce_scr(zip_file)

    # action_print(original_project)

    modified_project = between_step(original_project, scene, script)

    # action_print(modified_project)

    return modified_project
