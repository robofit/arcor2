from typing import Dict, List, NamedTuple, Optional, Set, Union

from arcor2.cached import CachedProject
from arcor2.data.common import Action, LogicItem, ProjectFunction
from arcor2.exceptions import Arcor2Exception

LogicContainer = Union[CachedProject, ProjectFunction]
ActionCache = Dict[str, Action]
LogicCache = Dict[str, LogicItem]
ActionIo = Dict[str, List[LogicItem]]

# TODO def validate_logic() -> to be called before saving project / building the package


class ActionCacheTuple(NamedTuple):  # TODO this will be probably obsolete once there will be CachedProjectFunction?

    actions: ActionCache
    logic: LogicCache

    action_inputs: ActionIo
    action_outputs: ActionIo

    first_logic_item: Optional[LogicItem] = None
    last_logic_item: Optional[LogicItem] = None

    @classmethod
    def from_logic_container(cls, container: LogicContainer) -> "ActionCacheTuple":

        actions_cache: ActionCache = {}
        logic_cache: LogicCache = {}
        first_logic_item: Optional[LogicItem] = None
        last_logic_item: Optional[LogicItem] = None

        action_inputs: ActionIo = {}
        action_outputs: ActionIo = {}

        for act in container.actions:
            actions_cache[act.id] = act

        for act in actions_cache.values():
            action_inputs[act.id] = []
            action_outputs[act.id] = []

        valid_endpoints = {LogicItem.START, LogicItem.END} | actions_cache.keys()

        for logic_item in container.logic:

            if logic_item.start not in valid_endpoints:
                raise Arcor2Exception(f"Logic item '{logic_item.id}' has invalid start.")

            if logic_item.end not in valid_endpoints:
                raise Arcor2Exception(f"Logic item '{logic_item.id}' has invalid end.")

            if logic_item.start == logic_item.START:
                if first_logic_item:
                    raise Arcor2Exception("Duplicate start.")
                first_logic_item = logic_item
            elif logic_item.end == logic_item.END:
                if last_logic_item:
                    raise Arcor2Exception("Duplicate end.")
                last_logic_item = logic_item
            else:
                start = logic_item.parse_start()
                action_outputs[start.start_action_id].append(logic_item)
                action_inputs[logic_item.end].append(logic_item)

            logic_cache[logic_item.id] = logic_item

        if first_logic_item and first_logic_item.id not in logic_cache:
            raise Arcor2Exception("Unknown start.")

        if last_logic_item and last_logic_item.id not in logic_cache:
            raise Arcor2Exception("Unknown end.")

        return ActionCacheTuple(actions_cache, logic_cache, action_inputs,
                                action_outputs, first_logic_item, last_logic_item)


def check_for_loops(parent: LogicContainer, first_action_id: Optional[str] = None) -> None:

    visited_actions: Set[str] = set()
    cache = ActionCacheTuple.from_logic_container(parent)

    def _check_for_loops(action: Action) -> None:

        if action.id in visited_actions:
            raise Arcor2Exception("Loop detected!")

        visited_actions.add(action.id)

        for output in cache.action_outputs[action.id]:
            if output.end == output.END:
                continue

            _check_for_loops(cache.actions[output.end])

    if not first_action_id:
        if not cache.first_logic_item:
            raise Arcor2Exception("Can't check unfinished logic.")

        first_action = cache.actions[cache.first_logic_item.end]
    else:
        first_action = cache.actions[first_action_id]

    _check_for_loops(first_action)
