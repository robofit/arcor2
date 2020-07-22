from typing import Set

from typed_ast.ast3 import Module, Pass

import arcor2.object_types
from arcor2.cached import CachedProject as CProject, CachedScene as CScene
from arcor2.exceptions import Arcor2Exception
from arcor2.helpers import camel_case_to_snake_case
from arcor2.logic import ActionCacheTuple
from arcor2.source import SCRIPT_HEADER, SourceException
from arcor2.source.object_types import fix_object_name
from arcor2.source.object_types import object_instance_from_res
from arcor2.source.utils import add_import, append_method_call, clean, empty_script_tree, get_name_attr,\
    main_loop_body, tree_to_str


def program_src(project: CProject, scene: CScene, built_in_objects: Set[str], add_logic: bool = True) -> str:

    tree = empty_script_tree(add_main_loop=add_logic)

    # get object instances from resources object
    for obj in scene.objects:

        if obj.type in built_in_objects:
            add_import(tree, arcor2.object_types.__name__, obj.type, try_to_import=False)
        else:
            add_import(tree, "object_types." + camel_case_to_snake_case(obj.type), obj.type, try_to_import=False)

        object_instance_from_res(tree, obj.name, obj.id, obj.type, "objects")

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

        ac_obj, ac_type = act.type.split('/')

        # for scene objects, convert ID to name
        try:
            ac_obj = scene.object(ac_obj).name
        except Arcor2Exception:
            pass

        append_method_call(loop, fix_object_name(ac_obj), ac_type, [get_name_attr("res", clean(act.name))], [])
