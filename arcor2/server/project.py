import asyncio
from typing import AsyncIterator, Dict, List, Set, Union

from arcor2 import helpers as hlp
from arcor2.cached import CachedProject, CachedScene, UpdateableCachedProject
from arcor2.clients import aio_persistent_storage as storage
from arcor2.data import common, events, object_type
from arcor2.exceptions import Arcor2Exception
from arcor2.parameter_plugins import PARAM_PLUGINS
from arcor2.parameter_plugins.base import ParameterPluginException
from arcor2.server import globals as glob, notifications as notif
from arcor2.server.scene import clear_scene, open_scene


async def close_project(do_cleanup: bool = True) -> None:

    glob.PROJECT = None
    await clear_scene(do_cleanup)
    asyncio.ensure_future(notif.broadcast_event(events.ProjectClosed()))


def check_action_params(scene: CachedScene, project: CachedProject, action: common.Action,
                        object_action: object_type.ObjectAction) -> None:

    _, action_type = action.parse_type()

    assert action_type == object_action.name

    if len(object_action.parameters) != len(action.parameters):
        raise Arcor2Exception("Unexpected number of parameters.")

    for req_param in object_action.parameters:

        param = action.parameter(req_param.name)

        if param.type == common.ActionParameter.TypeEnum.CONSTANT:

            const = project.constant(param.value)

            param_meta = object_action.parameter(param.id)
            if param_meta.type != const.type:
                raise Arcor2Exception("Param type does not match constant type.")

        elif param.type == common.ActionParameter.TypeEnum.LINK:

            assert param.type is None

            parsed_link = param.parse_link()
            outputs = project.action(parsed_link.action_id).flow(parsed_link.flow_name)

            assert len(outputs) == len(object_action.returns)

            param_meta = object_action.parameter(param.id)
            if param_meta.type != object_action.returns[parsed_link.output_index]:
                raise Arcor2Exception("Param type does not match action output type.")

        else:

            if param.type not in PARAM_PLUGINS:
                raise Arcor2Exception(f"Parameter {param.id} of action {action.name} has unknown type: {param.type}.")

            try:
                PARAM_PLUGINS[param.type].value(
                    {k: v.type_def for k, v in glob.OBJECT_TYPES.items() if v.type_def is not None},
                    scene, project, action.id, param.id)
            except ParameterPluginException as e:
                raise Arcor2Exception(f"Parameter {param.id} of action {action.name} has invalid value. {str(e)}")


def check_flows(parent: Union[CachedProject, common.ProjectFunction],
                action: common.Action, action_meta: object_type.ObjectAction) -> None:
    """
    Raises exception if there is something wrong with flow(s).
    :param parent:
    :param action:
    :param action_meta:
    :return:
    """

    flow = action.flow()  # searches default flow (just this flow is supported so far)

    if len(flow.outputs) != len(action_meta.returns):
        raise Arcor2Exception("Number of the flow outputs does not match the number of action outputs.")

    for output in flow.outputs:
        if not hlp.is_valid_identifier(output):
            raise Arcor2Exception(f"Output {output} is not a valid Python identifier.")

    outputs: Set[str] = set()

    for act in parent.actions:
        for fl in act.flows:
            for output in fl.outputs:
                if output in outputs:
                    raise Arcor2Exception(f"Output '{output}' is not unique.")


def find_object_action(scene: CachedScene, action: common.Action) -> object_type.ObjectAction:

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

        # action_ids: Set[str] = set()

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

        # valid_ids: Set[str] = action_ids | ActionIOEnum.set()

        # TODO remove invalid logic items

        await storage.update_project(project)
        updated_project_ids.add(project.id)

    await glob.logger.info("Updated projects: {}".format(updated_project_ids))


async def projects(scene_id: str) -> AsyncIterator[common.Project]:

    id_list = await storage.get_projects()

    for project_meta in id_list.items:

        project = await storage.get_project(project_meta.id)

        if project.scene_id != scene_id:
            continue

        yield project


def _project_using_object_as_parent(project: common.Project, obj_id: str) -> bool:

    for ap in project.action_points:
        if ap.parent == obj_id:
            return True

    return False


def _project_referencing_object(project: common.Project, obj_id: str) -> bool:

    for ap in project.action_points:
        for action in ap.actions:
            action_obj_id, _ = action.parse_type()

            if action_obj_id == obj_id:
                return True

    return False


async def projects_using_object(scene_id: str, obj_id: str) -> AsyncIterator[common.Project]:
    """
    Combines functionality of projects_using_object_as_parent and projects_referencing_object.
    :param scene_id:
    :param obj_id:
    :return:
    """

    async for project in projects(scene_id):
        if _project_using_object_as_parent(project, obj_id) or _project_referencing_object(project, obj_id):
            yield project


async def projects_using_object_as_parent(scene_id: str, obj_id: str) -> AsyncIterator[common.Project]:

    async for project in projects(scene_id):
        if _project_using_object_as_parent(project, obj_id):
            yield project


async def projects_referencing_object(scene_id: str, obj_id: str) -> AsyncIterator[common.Project]:

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

        for joints in ap.robot_joints:
            if not joints.is_valid:
                problems.append(f"Action point {ap.name} has invalid joints: {joints.name} "
                                f"(robot {joints.robot_id}).")

        for action in ap.actions:

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
                problems.append(f"Object type {scene_objects[obj_id]} does not have action {action_type} "
                                f"used in {action.id}.")
                continue

            try:
                check_action_params(scene, project, action, glob.OBJECT_TYPES[os_type].actions[action_type])
            except Arcor2Exception as e:
                problems.append(e.message)

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
        try:
            glob.SCENE.object(ap.parent)
        except Arcor2Exception:
            await clear_scene()
            raise Arcor2Exception(f"Action point's {ap.name} parent not available in the scene.")

    glob.PROJECT = project
