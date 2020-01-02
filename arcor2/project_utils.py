from typing import Tuple, Dict, Union

from arcor2.data.common import Project, Action, ActionIOEnum, ProjectObject, ActionPoint
from arcor2.helpers import camel_case_to_snake_case
from arcor2.exceptions import ActionPointNotFound, Arcor2Exception


class ProjectException(Arcor2Exception):
    pass


def get_actions_cache(project: Project) -> Tuple[Dict[str, Action], Union[str, None], Union[str, None]]:

    actions_cache = {}
    first_action_id = None
    last_action_id = None

    for obj in project.objects:
        for aps in obj.action_points:
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


def get_objects_cache(project: Project, id_to_var: bool = False) -> Dict[str, ProjectObject]:

    cache: Dict[str, ProjectObject] = {}

    for obj in project.objects:
        if id_to_var:
            cache[camel_case_to_snake_case(obj.id)] = obj
        else:
            cache[obj.id] = obj

    return cache


def clear_project_logic(project: Project) -> None:

    for obj in project.objects:
        for act_point in obj.action_points:
            for action in act_point.actions:
                action.inputs.clear()
                action.outputs.clear()


def get_object_ap(project: Project, ap_id: str) -> Tuple[ProjectObject, ActionPoint]:

    for obj in project.objects:
        for ap in obj.action_points:
            if ap.id == ap_id:
                return obj, ap

    raise ActionPointNotFound
