from typing import AsyncIterator

from arcor2.cached import CachedProject, UpdateableCachedProject
from arcor2.data import common
from arcor2_arserver import globals as glob
from arcor2_arserver import logger
from arcor2_arserver.clients import project_service as storage


async def scene_names() -> set[str]:
    return {scn.name for scn in (await storage.get_scenes())}


async def project_names() -> set[str]:
    return {proj.name for proj in (await storage.get_projects())}


async def associated_projects(scene_id: str) -> set[str]:
    return {project.id async for project in projects(scene_id)}


async def remove_object_references_from_projects(obj_id: str) -> None:

    assert glob.LOCK.scene

    updated_project_ids: set[str] = set()

    async for project in projects_using_object_as_parent(glob.LOCK.scene.id, obj_id):

        # action_ids: set[str] = set()

        # delete actions using the object
        for action_to_delete in {act.id for act in project.actions if act.parse_type()[0] == obj_id}:
            project.remove_action(action_to_delete)

        # delete actions using obj's action points as parameters
        # TODO fix this!
        """
        actions_using_invalid_param: set[str] = \
            {act.id for act in ap.actions for param in act.parameters
             if param.type in (ActionParameterTypeEnum.JOINTS, ActionParameterTypeEnum.POSE) and
             param.value.startswith(obj_id)}

        ap.actions = [act for act in ap.actions if act.id not in actions_using_invalid_param]

        # get IDs of remaining actions
        action_ids.update({act.id for act in ap.actions})
        """

        # valid_ids: set[str] = action_ids | ActionIOEnum.set()

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
