from typing import Set, Union

from horast import parse
from typed_ast.ast3 import Expr, Pass, Module, Call, Attribute

from arcor2.data.common import Project, Scene, Action, ActionIO, ActionIOEnum
from arcor2.helpers import camel_case_to_snake_case
from arcor2.project_utils import get_actions_cache, ProjectException
from arcor2.source import SCRIPT_HEADER, SourceException
from arcor2.source.object_types import fix_object_name
from arcor2.source.utils import main_loop_body, empty_script_tree, add_import, \
    append_method_call, tree_to_str, get_name_attr, clean
from arcor2.source.object_types import object_instance_from_res
import arcor2.object_types
from arcor2.exceptions import Arcor2Exception


def program_src(project: Project, scene: Scene, built_in_objects: Set[str], add_logic: bool = True) -> str:

    tree = empty_script_tree(add_main_loop=add_logic)

    # get object instances from resources object
    for obj in scene.objects:

        if obj.type in built_in_objects:
            add_import(tree, arcor2.object_types.__name__, obj.type, try_to_import=False)
        else:
            add_import(tree, "object_types." + camel_case_to_snake_case(obj.type), obj.type, try_to_import=False)

        object_instance_from_res(tree, obj.name, obj.id, obj.type, "objects")

    for srv in scene.services:
        add_import(tree, "services." + camel_case_to_snake_case(srv.type), srv.type, try_to_import=False)
        object_instance_from_res(tree, srv.type, srv.type, srv.type, "services")

    if add_logic:
        add_logic_to_loop(tree, scene, project)

    return SCRIPT_HEADER + tree_to_str(tree)


def get_logic_from_source(source_code: str, project: Project) -> None:

    tree = parse(source_code)

    assert isinstance(tree, Module)

    try:
        actions_cache, _, _ = get_actions_cache(project)
    except ProjectException as e:
        raise SourceException(e)
    # objects_cache = get_objects_cache(project, id_to_var=True)

    found_actions: Set[str] = set()

    loop = main_loop_body(tree)

    last_action: Union[None, Action] = None

    for node_idx, node in enumerate(loop):

        # simple checks for expected 'syntax' of action calls (e.g. 'robot.move_to(**res.MoveToBoxIN)')
        if not isinstance(node, Expr) or not isinstance(node.value, Call) or not isinstance(node.value.func, Attribute):
            raise SourceException("Unexpected content.")

        try:
            val = node.value
            obj_id = val.func.value.id  # type: ignore
            method = val.func.attr  # type: ignore
        except (AttributeError, IndexError) as e:
            print(e)
            raise SourceException("Script has unexpected content.")

        """
        Support for both:
            robot.move_to(res.MoveToBoxIN)  # args
        ...as well as
            robot.move_to(**res.MoveToBoxIN)  # kwargs
        """
        if len(val.args) == 1 and not val.keywords:
            action_id = val.args[0].attr  # type: ignore
        elif len(val.keywords) == 1 and not val.args:
            action_id = val.keywords[0].value.attr  # type: ignore
        else:
            raise SourceException("Unexpected argument(s) to the action.")

        if action_id in found_actions:
            raise SourceException(f"Duplicate action: {action_id}.")
        found_actions.add(action_id)

        # TODO test if object instance exists
        # raise GenerateSourceException(f"Unknown object id {obj_id}.")

        try:
            action = actions_cache[action_id]
        except KeyError:
            raise SourceException(f"Unknown action {action_id}.")

        at_obj, at_method = action.type.split("/")
        at_obj = camel_case_to_snake_case(at_obj)  # convert obj id into script variable name

        if at_obj != obj_id or at_method != method:
            raise SourceException(f"Action type {action.type} does not correspond to source, where it is"
                                  f" {obj_id}/{method}.")

        action.inputs.clear()
        action.outputs.clear()

        if node_idx == 0:
            action.inputs.append(ActionIO(ActionIOEnum.FIRST.value))
        else:
            assert last_action is not None
            action.inputs.append(ActionIO(last_action.id))

        if node_idx > 0:
            assert last_action is not None
            actions_cache[last_action.id].outputs.append(ActionIO(action.id))

        if node_idx == len(loop)-1:
            action.outputs.append(ActionIO(ActionIOEnum.LAST.value))

        last_action = action


def add_logic_to_loop(tree: Module, scene: Scene, project: Project) -> None:

    loop = main_loop_body(tree)

    try:
        actions_cache, first_action_id, last_action_id = get_actions_cache(project)
    except ProjectException as e:
        raise SourceException(e)

    if first_action_id is None:
        raise SourceException("'start' action not found.")

    if last_action_id is None:
        raise SourceException("'end' action not found.")

    next_action_id = first_action_id

    while True:

        act = actions_cache[next_action_id]

        if len(loop) == 1 and isinstance(loop[0], Pass):
            # pass is not necessary now
            loop.clear()

        ac_obj, ac_type = act.type.split('/')

        # for scene objects, convert ID to name
        try:
            ac_obj = scene.object(ac_obj).name
        except Arcor2Exception:
            pass

        append_method_call(loop, fix_object_name(ac_obj), ac_type, [get_name_attr("res", clean(act.name))], [])

        if act.id == last_action_id:
            break

        next_action_id = act.outputs[0].default
