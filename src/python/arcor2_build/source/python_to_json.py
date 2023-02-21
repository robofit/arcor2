import ast
import json
import logging
import sys
import tempfile
import zipfile
from ast import AnnAssign, Assign, Attribute, Call, Constant, Continue, Expr, If, Name, While

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
from arcor2.parameter_plugins.utils import plugin_from_type, plugin_from_type_name
from arcor2.source.utils import find_class_def
from arcor2.source.utils import parse as Parse
from arcor2_arserver.object_types.utils import object_actions
from arcor2_build.scripts.build import get_base_from_imported_package, read_dc_from_zip, read_str_from_zip
from arcor2_build.source.utils import find_Call, find_Compare, find_function_or_none, find_keyword, find_While
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


def get_pro_sce_scr(file: str):  # TODO: place somewhere else
    OBJECT_TYPE_MODULE = "arcor2_object_types"
    original_sys_path = list(sys.path)
    original_sys_modules = dict(sys.modules)

    project: Project
    scene: Scene
    script = None

    with zipfile.ZipFile(file + ".zip", "r") as zip_file:
        try:
            project = read_dc_from_zip(zip_file, "data/project.json", Project)
        except KeyError:
            print("Could not find project.json.")

        try:
            scene = read_dc_from_zip(zip_file, "data/scene.json", Scene)
        except KeyError:
            print("Could not find project.json.")

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


def get_parameters(
    rest_of_node: Call, variables: dict, file_func: str, original_project: Project, action_point: ActionPoint
):
    parameters = []

    position = file_func.find(".")  # split file.function(...) to file and function
    file = file_func[:position]
    func = file_func[position + 1 :]

    for from_file in objects:
        if find_function_or_none(func, ast.parse(objects[from_file].source)):  # where is that function stored
            break

    tmp = object_actions(object_type[file], ast.parse(objects[from_file].source))

    for j in range(len(rest_of_node.args)):
        f_name = tmp[func].parameters[j].name
        f_type = ""
        f_value = ""

        arg = rest_of_node.args[j]
        if isinstance(arg, Constant):  # constant
            f_type = tmp[func].parameters[j].type
            type = plugin_from_type_name(f_type)
            f_value = type.from_str_to_json(ast.unparse(arg))

        elif isinstance(arg, Attribute):  # class... it can by actionpoint
            f_type = tmp[func].parameters[j].type
            type = plugin_from_type_name(f_type)

            str_arg = ast.unparse(arg)
            if str_arg.find("aps.") == -1 and isinstance(arg.value, Name):
                class_node = find_class_def(arg.value.id, ast.parse(objects[from_file].source))  # find class

                for class_values in class_node.body:
                    if (
                        isinstance(class_values, AnnAssign)
                        and isinstance(class_values.target, Name)
                        and isinstance(class_values.annotation, Name)
                        and isinstance(class_values.value, Constant)
                    ):  # this conditon must by here becasue python dont know what is the type of these thinks
                        if arg.attr == class_values.target.id:
                            f_value = type.from_str_to_json(class_values.value.value)
            else:
                for ap in original_project.action_points:
                    if (
                        isinstance(arg, Attribute)
                        and isinstance(arg.value, Attribute)
                        and isinstance(arg.value.value, Attribute)
                    ):
                        if ap.name == arg.value.value.attr:
                            action_point = ap
                            if arg.value.attr == "poses":
                                f_value = type.from_str_to_json(ap.orientations[0].id)
                            elif arg.value.attr == "joints":
                                f_value = type.from_str_to_json(ap.robot_joints[0].id)
                            else:
                                f_value = type.from_str_to_json(ap.id)

        elif isinstance(arg, Name):  # variable definated in script or variable from project parameters
            arg_name = ast.unparse(arg)
            if arg_name in variables:
                f_type = ActionParameter.TypeEnum.LINK
                f_value = json.dumps(f"{variables[arg_name]}/default/0")
            else:
                for param in original_project.parameters:
                    if arg.id == param.name:
                        f_type = ActionParameter.TypeEnum.PROJECT_PARAMETER
                        f_value = json.dumps(param.id)

        parameters += [ActionParameter(f_name, f_type, f_value)]

    return parameters, action_point


def get_type(rest_of_node: Call, original_scene: Scene):
    file_func = ast.unparse(rest_of_node.func)
    # looking for type of action
    for object in original_scene.objects:
        if file_func.find(object.name + ".") != -1:
            # raplece name from code to scene definition
            type = file_func.replace(object.name + ".", (object.id + "/"))

            return type, file_func


def gen_actions(
    action_point: ActionPoint,
    node: Expr | Assign,
    variables: dict,
    original_scene: Scene,
    original_project: Project,
    flows: str = "",
):
    rest_of_node = find_Call(node)
    parameters = []

    final_flows = [Flow()]
    if flows:
        final_flows = [Flow(outputs=[(flows)])]

    name = ast.unparse(find_keyword(rest_of_node).value).replace("'", "")

    type, object_func = get_type(rest_of_node, original_scene)

    if rest_of_node.args != []:  # no args -> no parameters in fuction
        parameters, action_point = get_parameters(rest_of_node, variables, object_func, original_project, action_point)

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
    original_scene: Scene,
    original_project: Project,
) -> dict:

    rest_of_node = find_Compare(node)

    what_name = ast.unparse(rest_of_node.left)
    what = variables[what_name] + "/" + FlowTypes.DEFAULT + "/0"

    value_type = plugin_from_type(
        type(rest_of_node.comparators[0].value)
    )  # take type from condition and transforom it into arcor2 type
    value = value_type.from_str_to_json(ast.unparse(rest_of_node.comparators))

    if ac_id:  # node orelse
        gen_logic_for_if(ac_id, logic_list)

    else:  # node first if
        ac_id = logic_list[len(logic_list) - 1].start

    logic_list[len(logic_list) - 1].condition = ProjectLogicIf(f"{what}", value)
    variables = evaluate_nodes(action_point, logic_list, node, variables, original_scene, original_project)

    if node.orelse:
        # if node orelse contains "if" or "else" and not only "elif" this will find and evaluate all of them
        for else_or_if_node in node.orelse:
            if isinstance(else_or_if_node, If):
                variables = evaluate_if(
                    action_point, logic_list, else_or_if_node, variables, ac_id, original_scene, original_project
                )

    return variables


def evaluate_nodes(
    action_point: ActionPoint,
    logic_list: list,
    tree: If | While,
    variables: dict,
    original_scene: Scene,
    original_project: Project,
) -> dict:

    # if condition is on, then in future when should by generated new LogicItem,
    # will be chcek all nodes in logic_list and added id of next action as end of LogicItems
    # in case the condition is active and another node is "if"
    # that node will by processed as "elif" inside "evaluate_if"
    condition = False
    ac_id = ""

    for node in tree.body:

        if isinstance(node, Expr):
            ac_id, variables, action_point = gen_actions(
                action_point, node, variables, original_scene, original_project
            )

            if condition:
                gen_logic_after_if(ac_id, logic_list)
                condition = False
            else:
                gen_logic(ac_id, logic_list)

        elif isinstance(node, Assign):
            flows = ast.unparse(node.targets[0])
            ac_id, variables, action_point = gen_actions(
                action_point, node, variables, original_scene, original_project, flows
            )

            if condition:
                gen_logic_after_if(ac_id, logic_list)
                condition = False
            else:
                gen_logic(ac_id, logic_list)

        elif isinstance(node, If):
            if condition:
                variables = evaluate_if(
                    action_point, logic_list, node, variables, ac_id, original_scene, original_project
                )
            else:
                ac_id = logic_list[len(logic_list) - 1].start
                variables = evaluate_if(action_point, logic_list, node, variables, "", original_scene, original_project)
                condition = True

        elif isinstance(node, Continue):
            logic_list[len(logic_list) - 1].end = LogicItem.END

    return variables


def between_step(original_project: Project, original_scene: Scene, script: str):
    logic_list = list()
    start_item = LogicItem(LogicItem.START, "")
    logic_list.append(start_item)

    # dict of variables with id actions, where variable was declared ['name':'id', 'name':'id', ...]
    variables: dict[str, str] = {}  # TODO: separate module/class within arcor2_build
    tree = ast.parse(script)
    while_node = find_While(tree)

    ########################################
    for action_points in original_project.action_points:
        action_points.actions = []
    ########################################

    ap = original_project.action_points[0]
    evaluate_nodes(ap, logic_list, while_node, variables, original_scene, original_project)

    # adding END in to LogicItem with empty end
    original_project.logic = []
    for j in logic_list:
        if j.end == "":
            j.end = LogicItem.END

        original_project.logic.append(j)

    # print(variables)

    return original_project


def python_to_json(file: str) -> Project:

    original_project, original_scene, script = get_pro_sce_scr(file)

    # action_print(original_project)

    modified_project = between_step(original_project, original_scene, script)

    logic_print(modified_project)

    return modified_project
