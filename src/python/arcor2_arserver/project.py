import asyncio
from dataclasses import dataclass
from datetime import datetime
from typing import Any, AsyncIterator, Callable, Dict, List, Optional, Set

from arcor2 import helpers as hlp
from arcor2.action import results_to_json
from arcor2.cached import CachedProject, CachedScene, UpdateableCachedProject
from arcor2.data import common
from arcor2.exceptions import Arcor2Exception
from arcor2_arserver import globals as glob
from arcor2_arserver import logger
from arcor2_arserver import notifications as notif
from arcor2_arserver.checks import project_problems
from arcor2_arserver.clients import project_service as storage
from arcor2_arserver.objects_actions import get_object_types
from arcor2_arserver.scene import SceneProblems, get_ot_modified, get_scene_state, open_scene
from arcor2_arserver_data.events.actions import ActionExecution, ActionResult
from arcor2_arserver_data.events.common import ShowMainScreen
from arcor2_arserver_data.events.project import OpenProject, ProjectClosed


@dataclass
class ProjectProblems(SceneProblems):
    project_modified: datetime


_project_problems: Dict[str, ProjectProblems] = {}


async def get_project_problems(scene: CachedScene, project: CachedProject) -> Optional[List[str]]:
    """Handle caching of project problems."""

    assert scene.modified
    assert project.modified

    ots = scene.object_types
    await get_object_types()
    ot_modified = get_ot_modified(ots)

    if (
        project.id not in _project_problems
        or _project_problems[project.id].scene_modified < scene.modified
        or _project_problems[project.id].project_modified < project.modified
        or _project_problems[project.id].ot_modified != ot_modified
    ):

        logger.debug(f"Updating project_problems for {project.name}.")

        _project_problems[project.id] = ProjectProblems(
            scene.modified,
            project_problems(glob.OBJECT_TYPES, scene, project),
            ot_modified,
            project.modified,
        )

    # prune removed projects
    for csi in set(_project_problems.keys()) - await storage.get_project_ids():
        logger.debug(f"Pruning cached problems for removed project {csi}.")
        _project_problems.pop(csi, None)

    sp = _project_problems[project.id].problems

    return sp if sp else None


async def notify_project_opened(evt: OpenProject) -> None:

    await notif.broadcast_event(evt)
    await notif.broadcast_event(get_scene_state())


async def notify_project_closed(project_id: str) -> None:

    proj_list = ShowMainScreen.Data.WhatEnum.ProjectsList

    await notif.broadcast_event(ProjectClosed())
    glob.MAIN_SCREEN = ShowMainScreen.Data(proj_list)
    await notif.broadcast_event(ShowMainScreen(ShowMainScreen.Data(proj_list, project_id)))


async def close_project() -> None:

    assert glob.LOCK.project

    project_id = glob.LOCK.project.project.id
    glob.LOCK.scene = None
    glob.LOCK.project = None
    glob.PREV_RESULTS.clear()
    asyncio.ensure_future(notify_project_closed(project_id))


async def execute_action(action_method: Callable, params: List[Any]) -> None:

    assert glob.RUNNING_ACTION

    await notif.broadcast_event(ActionExecution(ActionExecution.Data(glob.RUNNING_ACTION)))

    evt = ActionResult(ActionResult.Data(glob.RUNNING_ACTION))

    try:
        action_result = await hlp.run_in_executor(action_method, *params)
    except Arcor2Exception as e:
        logger.error(f"Failed to run method {action_method.__name__} with params {params}. {str(e)}")
        logger.debug(str(e), exc_info=True)
        evt.data.error = str(e)
    else:

        if action_result is not None:

            glob.PREV_RESULTS[glob.RUNNING_ACTION] = action_result

            try:
                evt.data.results = results_to_json(action_result)
            except Arcor2Exception:
                logger.error(f"Method {action_method.__name__} returned unsupported type of result: {action_result}.")

    if glob.RUNNING_ACTION is None:
        # action was cancelled, do not send any event
        return  # type: ignore  # action could be cancelled during its execution

    glob.RUNNING_ACTION = None
    glob.RUNNING_ACTION_PARAMS = None
    await notif.broadcast_event(evt)


async def project_names() -> Set[str]:
    return {proj.name for proj in (await storage.get_projects())}


async def associated_projects(scene_id: str) -> Set[str]:
    return {project.id async for project in projects(scene_id)}


async def remove_object_references_from_projects(obj_id: str) -> None:

    assert glob.LOCK.scene

    updated_project_ids: Set[str] = set()

    async for project in projects_using_object_as_parent(glob.LOCK.scene.id, obj_id):

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

        await storage.update_project(project)
        updated_project_ids.add(project.id)

    logger.info("Updated projects: {}".format(updated_project_ids))


async def projects(scene_id: str) -> AsyncIterator[UpdateableCachedProject]:

    for project_meta in await storage.get_projects():

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

    assert glob.LOCK.scene

    # Invalidates robot joints if action point's parent has changed its pose.
    async for project in projects_using_object_as_parent(glob.LOCK.scene.id, obj.id):

        for ap in project.action_points:

            if ap.parent != obj.id:
                continue

            logger.debug(f"Invalidating joints for {project.name}/{ap.name}.")
            project.invalidate_joints(ap.id)

        await storage.update_project(project)


async def projects_referencing_object(scene_id: str, obj_id: str) -> AsyncIterator[CachedProject]:

    async for project in projects(scene_id):
        if _project_referencing_object(project, obj_id):
            yield project


async def open_project(project_id: str) -> None:

    project = await storage.get_project(project_id)

    if glob.LOCK.scene:
        if glob.LOCK.scene.id != project.scene_id:
            raise Arcor2Exception("Required project is associated to another scene.")
    else:
        await open_scene(project.scene_id)

    assert glob.LOCK.scene

    if pp := await get_project_problems(glob.LOCK.scene, project):
        glob.LOCK.scene = None
        logger.warning(f"Project {project.name} can't be opened due to the following problem(s)...")
        for ppp in pp:
            logger.warning(ppp)
        raise Arcor2Exception("Project has some problems.")

    glob.LOCK.project = UpdateableCachedProject(project)
