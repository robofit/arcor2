from typing import Set

import humps  # type: ignore
from typed_ast.ast3 import Module, Pass

import arcor2.object_types
from arcor2.cached import CachedProject as CProject
from arcor2.cached import CachedScene as CScene
from arcor2.exceptions import Arcor2Exception
from arcor2.helpers import is_valid_identifier
from arcor2.logic import ActionCacheTuple
from arcor2.source import SCRIPT_HEADER, SourceException
from arcor2.source.utils import add_import, append_method_call, get_name_attr, tree_to_str
from arcor2_build.source.object_types import object_instance_from_res
from arcor2_build.source.utils import clean, empty_script_tree, main_loop_body


def program_src(project: CProject, scene: CScene, built_in_objects: Set[str], add_logic: bool = True) -> str:

    tree = empty_script_tree(add_main_loop=add_logic)

    # get object instances from resources object
    for obj in scene.objects:

        if obj.type in built_in_objects:
            add_import(tree, arcor2.object_types.__name__, obj.type, try_to_import=False)
        else:
            add_import(tree, "object_types." + humps.depascalize(obj.type), obj.type, try_to_import=False)

        object_instance_from_res(tree, obj.name, obj.id, obj.type)

    if add_logic:
        add_logic_to_loop(tree, scene, project)

    return SCRIPT_HEADER + tree_to_str(tree)


def add_logic_to_loop(tree: Module, scene: CScene, project: CProject) -> None:

    loop = main_loop_body(tree)

    try:
        cache = ActionCacheTuple.from_logic_container(project)
    except Arcor2Exception as e:
        raise SourceException(e) from e

    if not cache.first_logic_item:
        raise SourceException("Can't process unfinished logic.")

    next_logic_item = cache.first_logic_item

    while True:

        if next_logic_item.end != next_logic_item.END:
            act = cache.actions[next_logic_item.end]
        else:
            break

        for logic_item in cache.logic.values():
            if logic_item.start == act.id:
                next_logic_item = logic_item
                break
        else:
            raise Arcor2Exception("Next logic item not found.")

        if len(loop) == 1 and isinstance(loop[0], Pass):
            # pass is not necessary now
            loop.clear()

        ac_obj, ac_type = act.type.split("/")

        # for scene objects, convert ID to name
        ac_obj = scene.object(ac_obj).name

        if not is_valid_identifier(ac_obj):
            raise Arcor2Exception(f"Object name {ac_obj} is not a valid identifier.")

        append_method_call(loop, ac_obj, ac_type, [get_name_attr("res", clean(act.name))], [])
