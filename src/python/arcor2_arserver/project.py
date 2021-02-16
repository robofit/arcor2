import asyncio
from typing import Any, AsyncIterator, Callable, Dict, List, Set, Tuple, Union

from arcor2 import helpers as hlp
from arcor2.action import results_to_json
from arcor2.cached import CachedProject, CachedScene, UpdateableCachedProject
from arcor2.data import common
from arcor2.exceptions import Arcor2Exception
from arcor2.parameter_plugins import ParameterPluginException
from arcor2.parameter_plugins.utils import known_parameter_types, plugin_from_type_name
from arcor2_arserver import globals as glob
from arcor2_arserver import notifications as notif
from arcor2_arserver.clients import persistent_storage as storage
from arcor2_arserver.objects_actions import get_types_dict
from arcor2_arserver.scene import open_scene
from arcor2_arserver_data.events.actions import ActionExecution, ActionResult
from arcor2_arserver_data.events.common import ShowMainScreen
from arcor2_arserver_data.events.project import ProjectClosed
from arcor2_arserver_data.objects import ObjectAction

PREV_RESULTS: Dict[str, Union[Tuple[Any], Any]] = {}


def remove_prev_result(action_id: str) -> None:

    try:
        del PREV_RESULTS[action_id]
    except KeyError:
        pass


async def notify_project_closed(project_id: str) -> None:

    proj_list = ShowMainScreen.Data.WhatEnum.ProjectsList

    await notif.broadcast_event(ProjectClosed())
    glob.MAIN_SCREEN = ShowMainScreen.Data(proj_list)
    await notif.broadcast_event(ShowMainScreen(ShowMainScreen.Data(proj_list, project_id)))


async def close_project() -> None:

    assert glob.PROJECT

    project_id = glob.PROJECT.project.id
    glob.SCENE = None
    glob.PROJECT = None
    PREV_RESULTS.clear()
    asyncio.ensure_future(notify_project_closed(project_id))


async def execute_action(action_method: Callable, params: List[Any]) -> None:

    assert glob.RUNNING_ACTION

    await notif.broadcast_event(ActionExecution(ActionExecution.Data(glob.RUNNING_ACTION)))

    evt = ActionResult(ActionResult.Data(glob.RUNNING_ACTION))

    try:
        action_result = await hlp.run_in_executor(action_method, *params)
    except (Arcor2Exception, AttributeError, TypeError) as e:
        glob.logger.error(f"Failed to run method {action_method.__name__} with params {params}. {str(e)}")
        glob.logger.debug(str(e), exc_info=True)
        evt.data.error = str(e)
    else:
        if action_result is not None:
            PREV_RESULTS[glob.RUNNING_ACTION] = action_result

        try:
            evt.data.results = results_to_json(action_result)
        except Arcor2Exception:
            glob.logger.error(f"Method {action_method.__name__} returned unsupported type of result: {action_result}.")

    if glob.RUNNING_ACTION is None:
        # action was cancelled, do not send any event
        return  # type: ignore  # action could be cancelled during its execution

    await notif.broadcast_event(evt)
    glob.RUNNING_ACTION = None
    glob.RUNNING_ACTION_PARAMS = None


def check_action_params(
    scene: CachedScene, project: CachedProject, action: common.Action, object_action: ObjectAction
) -> None:

    _, action_type = action.parse_type()

    assert action_type == object_action.name

    if len(object_action.parameters) != len(action.parameters):
        raise Arcor2Exception("Unexpected number of parameters.")

    for req_param in object_action.parameters:

        param = action.parameter(req_param.name)

        if param.type == common.ActionParameter.TypeEnum.CONSTANT:

            const = project.constant(param.value)

            param_meta = object_action.parameter(param.name)
            if param_meta.type != const.type:
                raise Arcor2Exception("Param type does not match constant type.")

        elif param.type == common.ActionParameter.TypeEnum.LINK:

            parsed_link = param.parse_link()
            outputs = project.action(parsed_link.action_id).flow(parsed_link.flow_name).outputs

            assert len(outputs) == len(object_action.returns)

            param_meta = object_action.parameter(param.name)
            if param_meta.type != object_action.returns[parsed_link.output_index]:
                raise Arcor2Exception("Param type does not match action output type.")

        else:

            if param.type not in known_parameter_types():
                raise Arcor2Exception(f"Parameter {param.name} of action {action.name} has unknown type: {param.type}.")

            try:
                plugin_from_type_name(param.type).parameter_value(
                    get_types_dict(), scene, project, action.id, param.name
                )
            except ParameterPluginException as e:
                raise Arcor2Exception(f"Parameter {param.name} of action {action.name} has invalid value. {str(e)}")


def check_flows(
    parent: Union[CachedProject, common.ProjectFunction], action: common.Action, action_meta: ObjectAction
) -> None:
    """Raises exception if there is something wrong with flow(s).

    :param parent:
    :param action:
    :param action_meta:
    :return:
    """

    flow = action.flow()  # searches default flow (just this flow is supported so far)

    # it is ok to not specify any output (if the values are not going to be used anywhere)
    # return value(s) won't be stored in variable(s)
    if not flow.outputs:
        return

    # otherwise, all return values have to be stored in variables
    if len(flow.outputs) != len(action_meta.returns):
        raise Arcor2Exception("Number of the flow outputs does not match the number of action outputs.")

    for output in flow.outputs:
        hlp.is_valid_identifier(output)

    outputs: Set[str] = set()

    for act in parent.actions:
        for fl in act.flows:
            for output in fl.outputs:
                if output in outputs:
                    raise Arcor2Exception(f"Output '{output}' is not unique.")


def find_object_action(scene: CachedScene, action: common.Action) -> ObjectAction:

    obj_id, action_type = action.parse_type()
    obj = scene.object(obj_id)

    try:
        obj_type = glob.OBJECT_TYPES[obj.type]
    except KeyError:
        raise Arcor2Exception("Unknown object type.")

    try:
        act = obj_type.actions[action_type]
    except KeyError:
        raise Arcor2Exception("Unknown type of action.")

    if act.disabled:
        raise Arcor2Exception("Action is disabled.")

    return act


async def project_names() -> Set[str]:
    return {proj.name for proj in (await storage.get_projects()).items}


async def associated_projects(scene_id: str) -> Set[str]:
    return {project.id async for project in projects(scene_id)}


async def remove_object_references_from_projects(obj_id: str) -> None:

    assert glob.SCENE

    updated_project_ids: Set[str] = set()

    async for project in projects_using_object_as_parent(glob.SCENE.id, obj_id):

        # action_ids: Set[str] = set()

        # delete actions using the object
        for action_to_delete in {act.id for act in project.actions if act.parse_type()[0] == obj_id}:
            project.remove_action(action_to_delete)

        # delete actions using obj's action points as parameters
        # TODO fix this!
        """
        actions_using_invalid_param: Set[str] = \
            {act.id for act in ap.actions for param in act.parameters
             if param.type in (ActionParameterTypeEnum.JOINTS, ActionParameterTypeEnum.POSE) and
             param.value.startswith(obj_id)}

        ap.actions = [act for act in ap.actions if act.id not in actions_using_invalid_param]

        # get IDs of remaining actions
        action_ids.update({act.id for act in ap.actions})
        """

        # valid_ids: Set[str] = action_ids | ActionIOEnum.set()

        # TODO remove invalid logic items

        await storage.update_project(project.project)
        updated_project_ids.add(project.id)

    glob.logger.info("Updated projects: {}".format(updated_project_ids))


async def projects(scene_id: str) -> AsyncIterator[UpdateableCachedProject]:

    id_list = await storage.get_projects()

    for project_meta in id_list.items:

        project = await storage.get_project(project_meta.id)

        if project.scene_id != scene_id:
            continue

        yield UpdateableCachedProject(project)


def _project_using_object_as_parent(project: CachedProject, obj_id: str) -> bool:

    for ap in project.action_points:
        if ap.parent == obj_id:
            return True

    return False


def _project_referencing_object(project: CachedProject, obj_id: str) -> bool:

    for action in project.actions:
        action_obj_id, _ = action.parse_type()

        if action_obj_id == obj_id:
            return True

    return False


async def projects_using_object(scene_id: str, obj_id: str) -> AsyncIterator[UpdateableCachedProject]:
    """Combines functionality of projects_using_object_as_parent and
    projects_referencing_object.

    :param scene_id:
    :param obj_id:
    :return:
    """

    async for project in projects(scene_id):
        if _project_using_object_as_parent(project, obj_id) or _project_referencing_object(project, obj_id):
            yield project


async def projects_using_object_as_parent(scene_id: str, obj_id: str) -> AsyncIterator[UpdateableCachedProject]:

    async for project in projects(scene_id):
        if _project_using_object_as_parent(project, obj_id):
            yield project


async def invalidate_joints_using_object_as_parent(obj: common.SceneObject) -> None:

    assert glob.SCENE

    # Invalidates robot joints if action point's parent has changed its pose.
    async for project in projects_using_object_as_parent(glob.SCENE.id, obj.id):

        for ap in project.action_points:

            if ap.parent != obj.id:
                continue

            glob.logger.debug(f"Invalidating joints for {project.name}/{ap.name}.")
            project.invalidate_joints(ap.id)

        await storage.update_project(project.project)


async def projects_referencing_object(scene_id: str, obj_id: str) -> AsyncIterator[CachedProject]:

    async for project in projects(scene_id):
        if _project_referencing_object(project, obj_id):
            yield project


def project_problems(scene: CachedScene, project: CachedProject) -> List[str]:

    scene_objects: Dict[str, str] = {obj.id: obj.type for obj in scene.objects}

    action_ids: Set[str] = set()
    problems: List[str] = []

    unknown_types = {obj.type for obj in scene.objects} - glob.OBJECT_TYPES.keys()

    if unknown_types:
        return [f"Scene invalid, contains unknown types: {unknown_types}."]

    for ap in project.action_points:

        # test if all objects exists in scene
        if ap.parent and ap.parent not in scene_objects:
            problems.append(f"Action point '{ap.name}' has parent '{ap.parent}' that does not exist in the scene.")
            continue

        for joints in project.ap_joints(ap.id):
            if not joints.is_valid:
                problems.append(
                    f"Action point {ap.name} has invalid joints: {joints.name} " f"(robot {joints.robot_id})."
                )

        for action in project.actions:

            if action.id in action_ids:
                problems.append(f"Action {action.name} of the {ap.name} is not unique.")

            # check if objects have used actions
            obj_id, action_type = action.parse_type()

            if obj_id not in scene_objects.keys():
                problems.append(f"Object ID {obj_id} which action is used in {action.name} does not exist in scene.")
                continue

            try:
                os_type = scene_objects[obj_id]  # object type
            except KeyError:
                os_type = obj_id  # service

            if action_type not in glob.OBJECT_TYPES[os_type].actions:
                problems.append(
                    f"Object type {scene_objects[obj_id]} does not have action {action_type} " f"used in {action.id}."
                )
                continue

            try:
                check_action_params(scene, project, action, glob.OBJECT_TYPES[os_type].actions[action_type])
            except Arcor2Exception as e:
                problems.append(str(e))

    return problems


async def open_project(project_id: str) -> None:

    project = UpdateableCachedProject(await storage.get_project(project_id))

    if glob.SCENE:
        if glob.SCENE.id != project.scene_id:
            raise Arcor2Exception("Required project is associated to another scene.")
    else:
        await open_scene(project.scene_id)

    assert glob.SCENE
    for ap in project.action_points_with_parent:

        assert ap.parent

        if ap.parent not in glob.SCENE.object_ids | project.action_points_ids:
            glob.SCENE = None
            raise Arcor2Exception(f"Action point's {ap.name} parent not available.")

    glob.PROJECT = project
