import logging
import os
from typing import Dict, Optional, Set, Union

import humps
from typed_ast.ast3 import Compare, Continue, Eq, FunctionDef, If, Load, Module, Name, NameConstant, Pass, While

import arcor2.object_types
from arcor2.cached import CachedProject as CProject
from arcor2.cached import CachedScene as CScene
from arcor2.data.common import Action, FlowTypes
from arcor2.logging import get_logger
from arcor2.source import SCRIPT_HEADER, SourceException
from arcor2.source.utils import add_import, add_method_call, get_name_attr, tree_to_str
from arcor2_build.source.object_types import object_instance_from_res
from arcor2_build.source.utils import clean, empty_script_tree, main_loop

logger = get_logger(__name__, logging.DEBUG if bool(os.getenv("ARCOR2_LOGIC_DEBUG", False)) else logging.INFO)


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


Container = Union[FunctionDef, If, While]  # TODO remove While


def add_logic_to_loop(tree: Module, scene: CScene, project: CProject) -> None:

    added_actions: Set[str] = set()

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

        add_method_call(
            container.body,
            ac_obj,
            act.action_type,
            [get_name_attr("res", clean(current_action.name))],
            [],
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
                blocks_to_start: Dict[str, int] = {}

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
                import json

                condition_value = json.loads(output.condition.value)
                comp = NameConstant(value=condition_value)
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
    assert added_actions == project.action_ids(), "Not all actions were added."

    if loop and isinstance(loop.body[0], Pass):
        # pass is not necessary now
        del loop.body[0]

    if loop and isinstance(loop.body[-1], Continue):
        # delete unnecessary continue
        del loop.body[-1]
