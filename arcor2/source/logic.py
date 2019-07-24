from typing import Set, Union

from horast import parse
from typed_ast.ast3 import Expr, Pass, keyword, Attribute, Name, Load

from arcor2.data import Project, Scene, Action, ActionIO, ActionIOEnum
from arcor2.helpers import convert_cc, get_actions_cache
from arcor2.source import SCRIPT_HEADER, SourceException
from arcor2.source.object_types import fix_object_name
from arcor2.source.utils import object_instance_from_res, main_loop_body, empty_script_tree, add_import, add_cls_inst, \
    append_method_call, tree_to_str


def program_src(project: Project, scene: Scene, built_in_objects: Set) -> str:

    tree = empty_script_tree()
    add_import(tree, "resources", "Resources", try_to_import=False)
    add_cls_inst(tree, "Resources", "res")

    # TODO api???
    # get object instances from resources object
    for obj in scene.objects:

        if obj.type in built_in_objects:
            add_import(tree, "arcor2.object_types", obj.type, try_to_import=False)
        else:
            add_import(tree, "object_types." + convert_cc(obj.type), obj.type, try_to_import=False)

        object_instance_from_res(tree, obj.id, obj.type)

    add_logic_to_loop(tree, project)

    return SCRIPT_HEADER + tree_to_str(tree)


def get_logic_from_source(source_code: str, project: Project) -> None:

    tree = parse(source_code)

    actions_cache, _, _ = get_actions_cache(project)
    # objects_cache = get_objects_cache(project, id_to_var=True)

    found_actions: Set[str] = set()

    loop = main_loop_body(tree)

    last_action: Union[None, Action] = None

    for node_idx, node in enumerate(loop):

        # simple checks for expected 'syntax' of action calls (e.g. 'robot.move_to(**res.MoveToBoxIN)')
        if not isinstance(node, Expr):
            raise SourceException("Unexpected content.")

        try:
            val = node.value
            obj_id = val.func.value.id  # variable name
            method = val.func.attr
            action_id = val.keywords[0].value.attr
        except (AttributeError, IndexError) as e:
            print(e)
            raise SourceException("Script has unexpected content.")

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
        at_obj = convert_cc(at_obj)  # convert obj id into script variable name

        if at_obj != obj_id or at_method != method:
            raise SourceException(f"Action type {action.type} does not correspond to source, where it is"
                                  f" {obj_id}/{method}.")

        action.inputs.clear()
        action.outputs.clear()

        if node_idx == 0:
            action.inputs.append(ActionIO(ActionIOEnum.FIRST))
        else:
            assert last_action is not None
            action.inputs.append(ActionIO(last_action.id))

        if node_idx > 0:
            assert last_action is not None
            actions_cache[last_action.id].outputs.append(ActionIO(action.id))

        if node_idx == len(loop)-1:
            action.outputs.append(ActionIO(ActionIOEnum.LAST))

        last_action = action


def add_logic_to_loop(tree, project: Project):

    loop = main_loop_body(tree)

    actions_cache, first_action_id, last_action_id = get_actions_cache(project)

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
        append_method_call(loop, fix_object_name(ac_obj), ac_type, [], [keyword(
                                                                      arg=None,
                                                                      value=Attribute(
                                                                        value=Name(
                                                                          id='res',
                                                                          ctx=Load()),
                                                                        attr=act.id,
                                                                        ctx=Load()))])

        if act.id == last_action_id:
            break

        next_action_id = act.outputs[0].default
