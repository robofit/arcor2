from typing import Tuple, Dict, Union

from arcor2.data.common import Project, Action, ActionIOEnum
from arcor2.exceptions import Arcor2Exception


class ProjectException(Arcor2Exception):
    pass


def get_actions_cache(project: Project) -> Tuple[Dict[str, Action], Union[str, None], Union[str, None]]:

    actions_cache = {}
    first_action_id = None
    last_action_id = None

    for aps in project.action_points:
        for act in aps.actions:
            actions_cache[act.id] = act
            if act.inputs and act.inputs[0].default == ActionIOEnum.FIRST.value:
                if first_action_id is not None:
                    raise ProjectException("Multiple starts.")
                first_action_id = act.id
            elif act.outputs and act.outputs[0].default == ActionIOEnum.LAST.value:
                if last_action_id is not None:
                    raise ProjectException("Multiple ends.")
                last_action_id = act.id

    if first_action_id not in actions_cache:
        raise ProjectException(f"Unknown start action: {first_action_id}.")

    if last_action_id not in actions_cache:
        raise ProjectException(f"Unknown end action: {last_action_id}.")

    return actions_cache, first_action_id, last_action_id


def clear_project_logic(project: Project) -> None:  # TODO method of Project class?

    for act_point in project.action_points:
        for action in act_point.actions:
            action.inputs.clear()
            action.outputs.clear()
