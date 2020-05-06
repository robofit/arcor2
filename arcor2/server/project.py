from typing import Set, AsyncIterator, List, Dict

from arcor2.data.common import ActionIOEnum, Project, Scene
import arcor2.aio_persistent_storage as storage
from arcor2.parameter_plugins import PARAM_PLUGINS
from arcor2.parameter_plugins.base import ParameterPluginException
from arcor2.exceptions import Arcor2Exception

from arcor2.server import globals as glob
from arcor2.server.scene import open_scene, clear_scene


async def project_names() -> Set[str]:
    return {proj.name for proj in (await storage.get_projects()).items}


async def associated_projects(scene_id: str) -> Set[str]:
    return {project.id async for project in projects(scene_id)}


async def scene_object_pose_updated(scene_id: str, obj_id: str) -> None:
    """
    Invalidates robot joints if action point's parent has changed its pose.
    :param scene_id:
    :param obj_id:
    :return:
    """

    async for project in projects_using_object_as_parent(scene_id, obj_id):

        for ap in project.action_points:

            if ap.parent != obj_id:
                continue

            await glob.logger.debug(f"Invalidating joints for {project.name}/{ap.name}.")
            ap.invalidate_joints()

        await storage.update_project(project)


async def remove_object_references_from_projects(obj_id: str) -> None:

    assert glob.SCENE

    updated_project_ids: Set[str] = set()

    async for project in projects_using_object_as_parent(glob.SCENE.id, obj_id):

        action_ids: Set[str] = set()

        for ap in project.action_points:

            # delete actions using the object
            ap.actions = [act for act in ap.actions if act.parse_type()[0] != obj_id]

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

        valid_ids: Set[str] = action_ids | ActionIOEnum.set()

        # remove invalid inputs/outputs
        for ap in project.action_points:
            for act in ap.actions:
                act.inputs = [input for input in act.inputs if input.default in valid_ids]
                act.outputs = [output for output in act.outputs if output.default in valid_ids]

        await storage.update_project(project)
        updated_project_ids.add(project.id)

    await glob.logger.info("Updated projects: {}".format(updated_project_ids))


async def projects(scene_id: str) -> AsyncIterator[Project]:

    id_list = await storage.get_projects()

    for project_meta in id_list.items:

        project = await storage.get_project(project_meta.id)

        if project.scene_id != scene_id:
            continue

        yield project


def _project_using_object_as_parent(project: Project, obj_id: str) -> bool:

    for ap in project.action_points_with_parent:

        assert ap.parent

        if ap.parent == obj_id:
            return True

    return False


def _project_referencing_object(project: Project, obj_id: str) -> bool:

    for ap in project.action_points:
        for action in ap.actions:
            action_obj_id, _ = action.parse_type()

            if action_obj_id == obj_id:
                return True

    return False


async def projects_using_object(scene_id: str, obj_id: str) -> AsyncIterator[Project]:
    """
    Combines functionality of projects_using_object_as_parent and projects_referencing_object.
    :param scene_id:
    :param obj_id:
    :return:
    """

    async for project in projects(scene_id):
        if _project_using_object_as_parent(project, obj_id) or _project_referencing_object(project, obj_id):
            yield project


async def projects_using_object_as_parent(scene_id: str, obj_id: str) -> AsyncIterator[Project]:

    async for project in projects(scene_id):
        if _project_using_object_as_parent(project, obj_id):
            yield project


async def projects_referencing_object(scene_id: str, obj_id: str) -> AsyncIterator[Project]:

    async for project in projects(scene_id):
        if _project_referencing_object(project, obj_id):
            yield project


def project_problems(scene: Scene, project: Project) -> List[str]:

    scene_objects: Dict[str, str] = {obj.id: obj.type for obj in scene.objects}
    scene_services: Set[str] = {srv.type for srv in scene.services}

    action_ids: Set[str] = set()
    problems: List[str] = []

    unknown_types = ({obj.type for obj in scene.objects} | scene_services) - glob.ACTIONS.keys()

    if unknown_types:
        return [f"Scene invalid, contains unknown types: {unknown_types}."]

    for ap in project.action_points:

        # test if all objects exists in scene
        if ap.parent and ap.parent not in scene_objects:
            problems.append(f"Action point '{ap.name}' has parent '{ap.parent}' that does not exist in the scene.")
            continue

        for joints in ap.robot_joints:
            if not joints.is_valid:
                problems.append(f"Action point {ap.name} has invalid joints: {joints.name} "
                                f"(robot {joints.robot_id}).")

        for action in ap.actions:

            if action.id in action_ids:
                problems.append(f"Action ID {action.name} of the {ap.name} is not unique.")

            # check if objects have used actions
            obj_id, action_type = action.parse_type()

            if obj_id not in scene_objects.keys() | scene_services:
                problems.append(f"Object ID {obj_id} which action is used in {action.name} does not exist in scene.")
                continue

            try:
                os_type = scene_objects[obj_id]  # object type
            except KeyError:
                os_type = obj_id  # service

            for act in glob.ACTIONS[os_type]:
                if action_type == act.name:
                    break
            else:
                problems.append(f"Object type {scene_objects[obj_id]} does not have action {action_type} "
                                f"used in {action.id}.")

            # check object's actions parameters
            action_params: Dict[str, str] = \
                {param.id: param.type for param in action.parameters}
            ot_params: Dict[str, str] = {param.name: param.type for param in act.parameters
                                         for act in glob.ACTIONS[os_type]}

            if action_params != ot_params:
                problems.append(f"Action ID {action.id} of type {action.type} has invalid parameters.")

            # TODO validate parameter values / instances (for value) are not available here / how to solve it?
            for param in action.parameters:
                try:
                    PARAM_PLUGINS[param.type].value(glob.TYPE_DEF_DICT, scene, project, action.id, param.id)
                except ParameterPluginException:
                    problems.append(f"Parameter {param.id} of action {act.name} "
                                    f"has invalid value: '{param.value}'.")

    return problems


async def open_project(project_id: str) -> None:

    project = await storage.get_project(project_id)

    if glob.SCENE:
        if glob.SCENE.id != project.scene_id:
            raise Arcor2Exception("Required project is associated to another scene.")
    else:
        await open_scene(project.scene_id)

    assert glob.SCENE
    for ap in project.action_points_with_parent:

        assert ap.parent
        try:
            glob.SCENE.object(ap.parent)
        except Arcor2Exception:
            await clear_scene()
            raise Arcor2Exception(f"Action point's {ap.name} parent not available in the scene.")

    glob.PROJECT = project
