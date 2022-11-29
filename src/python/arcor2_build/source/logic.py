import logging
from ast import (
    AST,
    Assign,
    Compare,
    Continue,
    Eq,
    FunctionDef,
    If,
    Load,
    Module,
    Name,
    NameConstant,
    Num,
    Pass,
    Store,
    Str,
    While,
    expr,
    keyword,
)
from typing import Optional, Union

import humps

from arcor2 import env
from arcor2.cached import CachedProject as CProject
from arcor2.cached import CachedScene as CScene
from arcor2.data.common import Action, ActionParameter, FlowTypes
from arcor2.exceptions import Arcor2Exception
from arcor2.logging import get_logger
from arcor2.parameter_plugins.base import TypesDict
from arcor2.parameter_plugins.utils import plugin_from_type_name
from arcor2.source import SCRIPT_HEADER, SourceException
from arcor2.source.utils import add_import, add_method_call, tree_to_str
from arcor2_build.source.object_types import object_instance_from_res
from arcor2_build.source.utils import empty_script_tree, find_function, find_last_assign, main_loop

######################
import json
import ast

from arcor2.data.common import (
    Action,
    ActionParameter,
    ActionPoint,
    Flow,
    LogicItem,
    Position,
    Project,
    ProjectLogicIf,
    Scene,
)
from ast import (
    Call,
    Expr,
    While, 
    NodeVisitor,
    Constant
)
from arcor2.data.object_type import ObjectType
from llist import sllist

from arcor2_build.scripts.build import read_dc_from_zip, read_str_from_zip
import zipfile

#####################
objects: dict[str, ObjectType] = {}

logger = get_logger(__name__, logging.DEBUG if env.get_bool("ARCOR2_LOGIC_DEBUG", False) else logging.INFO)


def program_src(type_defs: TypesDict, project: CProject, scene: CScene, add_logic: bool = True) -> str:

    tree = empty_script_tree(project.id, add_main_loop=add_logic)

    # get object instances from resources object
    main = find_function("main", tree)
    last_assign = find_last_assign(main)
    for obj in scene.objects:
        add_import(tree, "object_types." + humps.depascalize(obj.type), obj.type, try_to_import=False)
        last_assign += 1
        main.body.insert(last_assign, object_instance_from_res(obj.name, obj.id, obj.type))

    # TODO temporary solution - should be (probably) handled by plugin(s)
    from arcor2 import json

    # TODO should we put there even unused parameters?
    for param in project.parameters:
        val = json.loads(param.value)

        aval: Optional[expr] = None

        if isinstance(val, bool):  # subclass of int
            aval = NameConstant(value=val, kind=None)
        elif isinstance(val, (int, float)):
            aval = Num(n=val, kind=None)
        elif isinstance(val, str):
            aval = Str(s=val, kind="")

        if not aval:
            raise Arcor2Exception(f"Unsupported project parameter type ({param.type}) or value ({val}).")

        last_assign += 1
        main.body.insert(
            last_assign,
            Assign(  # TODO use rather AnnAssign?
                targets=[Name(id=param.name, ctx=Store())], value=aval, type_comment=None
            ),
        )

    if add_logic:
        add_logic_to_loop(type_defs, tree, scene, project)

    return SCRIPT_HEADER + tree_to_str(tree)


Container = Union[FunctionDef, If, While]  # TODO remove While


def add_logic_to_loop(type_defs: TypesDict, tree: Module, scene: CScene, project: CProject) -> None:

    added_actions: set[str] = set()

    def _blocks_to_start(action: Action, depth: int = 0) -> int:

        inputs, outputs = project.action_io(action.id)

        for inp in inputs:
            if inp.start == inp.START:
                continue
            parsed_input = inp.parse_start()

            prev_action = project.action(parsed_input.start_action_id)
            _, prev_action_outputs = project.action_io(prev_action.id)

            if len(prev_action_outputs) > 1:
                depth += 1
            _blocks_to_start(prev_action, depth)

        return depth

    def _add_logic(container: Container, current_action: Action, super_container: Optional[Container] = None) -> None:

        # more paths could lead  to the same action, so it might be already added
        # ...this is easier than searching the tree
        if current_action.id in added_actions:
            logger.debug(f"Action {current_action.name} already added, skipping.")
            return

        inputs, outputs = project.action_io(current_action.id)
        logger.debug(f"Adding action {current_action.name}, with {len(inputs)} input(s) and {len(outputs)} output(s).")

        act = current_action.parse_type()
        ac_obj = scene.object(act.obj_id).name

        args: list[AST] = []

        # TODO make sure that the order of parameters is correct / re-order
        for param in current_action.parameters:

            if param.type == ActionParameter.TypeEnum.LINK:

                parsed_link = param.parse_link()
                parent_action = project.action(parsed_link.action_id)

                # TODO add support for tuples
                assert len(parent_action.flow(FlowTypes.DEFAULT).outputs) == 1, "Only one result is supported atm."
                assert parsed_link.output_index == 0

                res_name = parent_action.flow(FlowTypes.DEFAULT).outputs[0]

                # make sure that the result already exists
                if parent_action.id not in added_actions:
                    raise SourceException(
                        f"Action {current_action.name} attempts to use result {res_name} "
                        f"of subsequent action {parent_action.name}."
                    )

                args.append(Name(id=res_name, ctx=Load()))

            elif param.type == ActionParameter.TypeEnum.PROJECT_PARAMETER:
                args.append(Name(id=project.parameter(param.str_from_value()).name, ctx=Load()))
            else:

                plugin = plugin_from_type_name(param.type)

                args.append(plugin.parameter_ast(type_defs, scene, project, current_action.id, param.name))

                list_of_imp_tup = plugin.need_to_be_imported(type_defs, scene, project, current_action.id, param.name)

                if list_of_imp_tup:
                    # TODO what if there are two same names?
                    for imp_tup in list_of_imp_tup:
                        add_import(tree, imp_tup.module_name, imp_tup.class_name, try_to_import=False)

        add_method_call(
            container.body,
            ac_obj,
            act.action_type,
            args,
            [keyword(arg="an", value=Str(s=current_action.name, kind=""))],
            current_action.flow(FlowTypes.DEFAULT).outputs,
        )

        added_actions.add(current_action.id)

        if not outputs:
            raise SourceException(f"Action {current_action.name} has no outputs.")
        elif len(outputs) == 1:
            output = outputs[0]

            if output.end == output.END:
                # TODO this is just temporary (while there is while loop), should be rather Return()
                container.body.append(Continue())
                return

            seq_act = project.action(output.end)
            seq_act_inputs, _ = project.action_io(seq_act.id)
            if len(seq_act_inputs) > 1:  # the action belongs to a different block

                if seq_act.id in added_actions:
                    return

                logger.debug(f"Action {seq_act.name} going to be added to super_container.")

                # test if this is the correct super_container -> count distance (number of blocks) to the START
                blocks_to_start: dict[str, int] = {}

                for inp in seq_act_inputs:
                    parsed_start = inp.parse_start()
                    pact = project.action(parsed_start.start_action_id)
                    blocks_to_start[pact.id] = _blocks_to_start(pact)
                winner = min(blocks_to_start, key=blocks_to_start.get)  # type: ignore  # TODO what is wrong with it?

                # TODO if blocks_to_start is cached somewhere, the second part of the condition is useless
                # it might happen that there are two different ways with the same distance
                if winner == current_action.id or all(
                    value == list(blocks_to_start.values())[0] for value in blocks_to_start.values()
                ):
                    assert super_container is not None
                    _add_logic(super_container, seq_act)
                return

            logger.debug(f"Sequential action: {seq_act.name}")
            _add_logic(container, seq_act, super_container)

        else:

            root_if: Optional[If] = None

            # action has more outputs - each output should have condition
            for idx, output in enumerate(outputs):
                if not output.condition:
                    raise SourceException("Missing condition.")

                # TODO use parameter plugin (action metadata will be needed - to get the return types)
                # TODO support for other countable types
                # ...this will only work for booleans
                from arcor2 import json

                condition_value = json.loads(output.condition.value)
                comp = NameConstant(value=condition_value, kind=None)
                what = output.condition.parse_what()
                output_name = project.action(what.action_id).flow(what.flow_name).outputs[what.output_index]

                cond = If(
                    test=Compare(left=Name(id=output_name, ctx=Load()), ops=[Eq()], comparators=[comp]),
                    body=[],
                    orelse=[],
                )

                if idx == 0:
                    root_if = cond
                    container.body.append(root_if)
                    logger.debug(f"Adding branch for: {condition_value}")
                else:
                    assert isinstance(root_if, If)
                    root_if.orelse.append(cond)

                if output.end == output.END:
                    cond.body.append(Continue())  # TODO should be rather return
                    continue

                _add_logic(cond, project.action(output.end), container)

    current_action = project.action(project.first_action_id())
    # having 'while True' default loop is temporary solution until there will be support for functions/loops
    loop = main_loop(tree)
    _add_logic(loop, current_action)

    logger.debug(f"Unused actions: {[project.action(act_id).name for act_id in project.action_ids() - added_actions]}")

    if loop and isinstance(loop.body[0], Pass):
        # pass is not necessary now
        del loop.body[0]

    if loop and isinstance(loop.body[-1], Continue):
        # delete unnecessary continue
        del loop.body[-1]

###########################################################
def find_While(tree: Union[Module, AST]) -> While:
    class FindWhile(NodeVisitor):
        def __init__(self) -> None:
            self.While_node: Optional[While] = None

        def visit_While(self, node: While) -> None:
            self.While_node = node
            self.generic_visit(node)
            return

    ff = FindWhile()
    ff.visit(tree)

    return ff.While_node

def find_Call(tree: Union[Module, AST]) -> Call:
    class FindCall(NodeVisitor):
        def __init__(self) -> None:
            self.Call_node: Optional[Call] = None

        def visit_Call(self, node: Call) -> None:
            self.Call_node = node
            return

    ff = FindCall()
    ff.visit(tree)

    return ff.Call_node

def find_keyword(tree: Union[Module, AST]) -> keyword:
    class Findkeyword(NodeVisitor):
        def __init__(self) -> None:
            self.keyword_node: Optional[keyword] = None

        def visit_keyword(self, node: keyword) -> None:
            self.keyword_node = node
            return

    ff = Findkeyword()
    ff.visit(tree)

    return ff.keyword_node

def find_Compare(tree: Union[Module, AST]) -> list[Compare]:
    class FindCompare(NodeVisitor):
        def __init__(self) -> None:
            self.Compare_node: list[Compare] = []

        def visit_Compare(self, node: Compare) -> None:
            self.Compare_node.append(node)
            return

    ff = FindCompare()
    ff.visit(tree)

    return ff.Compare_node[0]

def get_pro_sce_scr(file):

    project=0
    scene=0
    script=0

    with zipfile.ZipFile(file+'.zip', 'r') as zip_file:
        try:
            project = read_dc_from_zip(zip_file, file+"/data/project.json", Project)
        except KeyError:
            print("Could not find project.json.")

        try:
            scene = read_dc_from_zip(zip_file, file+"/data/scene.json", Scene)
        except KeyError:
            print("Could not find project.json.")

        for scene_obj in scene.objects:
            obj_type_name = scene_obj.type
            if obj_type_name in objects:  # there might be more instances of the same type
                continue
            logger.debug(f"Importing {obj_type_name}.")

            try:
                obj_type_src = read_str_from_zip(zip_file, file+f"/object_types/{humps.depascalize(obj_type_name)}.py")
            except KeyError:
                print(f"Object type {obj_type_name} is missing in the package.")


        logger.debug("Importing the main script.")
        try:
            script = zip_file.read(file+"/script.py").decode("UTF-8")            
        except KeyError:
            print("Could not find script.py.")

        return project, scene, script

def gen_logic(ac_id, lst, condition = ""):

    if condition == "check_if":
        for i in range(lst.size):
            node = lst.nodeat(i)
            if node.value.end == '':
                node.value.end= ac_id
        item = LogicItem(ac_id, "")
        lst.append(item)

    elif condition == "add_if_LogicItem":
        item = LogicItem(ac_id, "")
        lst.append(item)

    else:
        lst.last.value.end = ac_id
        item = LogicItem(ac_id, "")
        lst.append(item)

    return

def gen_actions(ap1, node, variables: list, flows="", original_project=0, original_scene=0):
    parameters = []
    type = ""
    final_flows = [Flow()]

    rest_of_node = find_Call(node)

    # flow
    if flows:
        final_flows = [Flow(outputs=[(flows)])]

    # type
    tmp = ast.unparse(rest_of_node.func)
    length = len(original_scene.objects)
    #looking for type of action
    for i in range(length):
        if (tmp.find(original_scene.objects[i].name+".") != -1):   
            #raplece name from code to scene definition 
            type = tmp.replace(original_scene.objects[i].name+".",(original_scene.objects[i].id+"/"))
            break
    
    # name 
    name = ast.unparse(find_keyword(rest_of_node).value).replace("\'","")

    # parameters
    #TODO: value
    try:
        num_of_args = len(rest_of_node.args)
        num_of_variables = len(variables)
        for j in range(num_of_args):  
            condition = 0 
            arg = ast.unparse(rest_of_node.args[j])

            if isinstance(rest_of_node.args[j], Constant):      #TODO: constant from objects
                pass
                
            elif condition == 0:
                for i in range(len(original_project.parameters)):       #constant from scene
                    if arg == original_project.parameters[i].name:
                        parameters+=[ActionParameter("param", ActionParameter.TypeEnum.PROJECT_PARAMETER, json.dumps(original_project.parameters[i].id))]
                        condition = 1
                        break

            elif condition == 0:
                for i in range(num_of_variables):                       #variable
                    if  arg == variables[i]:
                        parameters+=[ActionParameter("param", ActionParameter.TypeEnum.LINK, json.dumps(f"{variables[i+1]}/default/0"))]
                        break
                    i += 1

    except:
        parameters=[]
  
    ac1 = Action(name, type, flows=final_flows, parameters=parameters)
    ap1.actions.append(ac1)   
        
    #adding variables to list with actions id
    if flows != Flow():
        variables.append(flows)     
        variables.append(ac1.id)
    
    return ac1.id, variables

def evaluate_if (ap1, lst, node, variables: list, ac_id = "", original_project =0, original_scene=0):

    rest_of_node = find_Compare(node)
    what = ast.unparse(rest_of_node.left)
    value = ast.unparse(rest_of_node.comparators)
    if value == "True":
        value="true"
    else:
        value="false"

    for i in range(len(variables)):
        if what == variables[i]:
            what = variables[i+1]+"/default/0"
            break
        i += 1

    #orelse 
    if ac_id:                        
        gen_logic(ac_id, lst, "add_if_LogicItem")   
    #first if
    else:  
        ac_id = lst.last.value.start

    lst.last.value.condition = ProjectLogicIf(f"{what}", value)
    variables = evaluate_nodes(ap1, lst, node, variables, original_project, original_scene)

    if node.orelse:
        #if node orelse contains "if" and "else" and not only "elif" this will find them all 
        for tmp_node in node.orelse:
            variables = evaluate_if(ap1, lst, tmp_node, variables, ac_id, original_project, original_scene)

    return variables

def evaluate_nodes(ap1: ActionPoint, lst: sllist, tree: Module, variables :list, original_project : Project, original_scene : Scene):
    
    #if condition is on, then in future generate LogicItems 
    # will be chcek all nodes in lst and added id of next action as end of LogicItems 
    # in case the condition is active and another node is "if" that node will by processed as "elif" inside "evaluate_if" 
    condition = 0
    ac_id = 0

    for node in tree.body:

        if isinstance(node, Expr):
            ac_id, variables = gen_actions(ap1, node, variables, "", original_project, original_scene)

            if condition == 1:
                gen_logic(ac_id, lst, "check_if")
                condition = 0
            else:
                gen_logic(ac_id, lst)

        elif isinstance(node, Assign):
            flows = ast.unparse(node.targets)
            ac_id, variables = gen_actions(ap1, node, variables, flows, original_project, original_scene)

            if condition == 1:
                gen_logic(ac_id, lst, "check_if")
                condition = 0
            else:
                gen_logic(ac_id, lst)
                
        elif isinstance(node, If):
            if condition == 0: 
                ac_id = lst.last.value.start
                variables = evaluate_if(ap1, lst, node, variables, "", original_project, original_scene)
                condition = 1
            else:
                variables = evaluate_if(ap1, lst, node, variables, ac_id, original_project, original_scene)

        elif isinstance(node, Continue):
            lst.last.value.end = LogicItem.END
                
    return variables

def python_to_json(file):
    # TODO: compare

    original_project, original_scene, script = get_pro_sce_scr(file)

    project = Project("p1", "s1")
    ap1 = ActionPoint("ap1", Position())
    project.action_points.append(ap1)

    #linked-list of LogicItems
    lst = sllist()
    start_item = LogicItem(LogicItem.START, "")
    lst.append(start_item)

    #list of variables with id actions, where variable was declared
    variables = []

    tree = ast.parse(script)
    tree = find_While(tree)
    evaluate_nodes(ap1, lst, tree, variables, original_project, original_scene)

    #adding END in to LogicItem with empty end
    for i in range(lst.size):    
        node = lst.nodeat(i)
        if node.value.end == '':
            node.value.end= LogicItem.END

        #adding logicitems to project
        project.logic.append(node.value)

    return project
#python_to_json('pkg_2ce3d90033994836a5ce4d083759645d')