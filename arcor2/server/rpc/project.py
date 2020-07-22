#!/usr/bin/env python3
# -*- coding: utf-8 -*-


import asyncio
import collections.abc as collections_abc
import copy
import inspect
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator, Callable, Dict, List, Optional

from websockets.server import WebSocketServerProtocol as WsClient

from arcor2 import helpers as hlp, transformations as tr
from arcor2.cached import CachedProjectException, CachedScene, UpdateableCachedProject
from arcor2.clients import aio_persistent_storage as storage
from arcor2.data import common, events, rpc
from arcor2.exceptions import Arcor2Exception
from arcor2.logic import LogicContainer, check_for_loops
from arcor2.object_types import utils as otu
from arcor2.parameter_plugins import PARAM_PLUGINS, TYPE_TO_PLUGIN
from arcor2.parameter_plugins.base import ParameterPluginException
from arcor2.server import globals as glob, notifications as notif, robot
from arcor2.server.decorators import no_project, project_needed, scene_needed
from arcor2.server.helpers import unique_name
from arcor2.server.project import check_action_params, check_flows, find_object_action, open_project, project_names,\
    project_problems
from arcor2.server.robot import get_end_effector_pose, get_robot_joints
from arcor2.server.scene import clear_scene, get_instance, open_scene
from arcor2.source import SourceException
from arcor2.source.logic import program_src


PREV_RESULTS: Dict[str, List[Any]] = {}


def remove_prev_result(action_id: str) -> None:

    try:
        del PREV_RESULTS[action_id]
    except KeyError:
        pass


@asynccontextmanager
async def managed_project(project_id: str, make_copy: bool = False) -> AsyncGenerator[UpdateableCachedProject, None]:

    save_back = False

    if glob.PROJECT and glob.PROJECT.id == project_id:
        if make_copy:
            project = copy.deepcopy(glob.PROJECT)
            save_back = True
        else:
            project = glob.PROJECT
    else:
        save_back = True
        project = UpdateableCachedProject(await storage.get_project(project_id))

    if make_copy:
        project.id = common.uid()

    try:
        yield project
    finally:
        if save_back:
            asyncio.ensure_future(storage.update_project(project.project))


@scene_needed
@project_needed
async def cancel_action_cb(req: rpc.project.CancelActionRequest, ui: WsClient) -> None:

    assert glob.SCENE
    assert glob.PROJECT

    if not glob.RUNNING_ACTION:
        raise Arcor2Exception("No action is running.")

    action = glob.PROJECT.action(glob.RUNNING_ACTION)
    obj_id, action_name = action.parse_type()
    obj = get_instance(obj_id)

    if not find_object_action(glob.SCENE, action).meta.cancellable:
        raise Arcor2Exception("Action is not cancellable.")

    try:
        action_method = getattr(obj, action_name)
        cancel_method = getattr(obj, obj.CANCEL_MAPPING[action_method.__name__])
    except AttributeError as e:
        raise Arcor2Exception("Internal error.") from e

    cancel_params: Dict[str, Any] = {}

    cancel_sig = inspect.signature(cancel_method)

    assert glob.RUNNING_ACTION_PARAMS is not None

    for param_name in cancel_sig.parameters.keys():
        try:
            cancel_params[param_name] = glob.RUNNING_ACTION_PARAMS[param_name]
        except KeyError as e:
            raise Arcor2Exception("Cancel method parameters should be subset of action parameters.") from e

    await hlp.run_in_executor(cancel_method, *cancel_params.values())

    asyncio.ensure_future(notif.broadcast_event(events.ActionCancelledEvent()))
    glob.RUNNING_ACTION = None
    glob.RUNNING_ACTION_PARAMS = None


async def execute_action(action_method: Callable, params: Dict[str, Any]) -> None:

    assert glob.RUNNING_ACTION

    await notif.broadcast_event(events.ActionExecutionEvent(data=events.ActionExecutionData(glob.RUNNING_ACTION)))

    evt = events.ActionResultEvent()
    evt.data.action_id = glob.RUNNING_ACTION

    try:
        action_result = await hlp.run_in_executor(action_method, *params.values())
    except Arcor2Exception as e:
        await glob.logger.error(e)
        evt.data.error = e.message
    except (AttributeError, TypeError) as e:
        await glob.logger.error(e)
        evt.data.error = str(e)
    else:
        if action_result is not None:
            PREV_RESULTS[glob.RUNNING_ACTION] = action_result
            try:
                evt.data.result = TYPE_TO_PLUGIN[type(action_result)].value_to_json(action_result)
            except KeyError:
                # TODO temporal workaround for unsupported types
                evt.data.result = str(action_result)

    if glob.RUNNING_ACTION is None:
        # action was cancelled, do not send any event
        return

    await notif.broadcast_event(evt)
    glob.RUNNING_ACTION = None
    glob.RUNNING_ACTION_PARAMS = None


@scene_needed
@project_needed
async def execute_action_cb(req: rpc.project.ExecuteActionRequest, ui: WsClient) -> None:

    assert glob.SCENE
    assert glob.PROJECT

    if glob.RUNNING_ACTION:
        raise Arcor2Exception(f"Action {glob.RUNNING_ACTION} is being executed. "
                              f"Only one action can be executed at a time.")

    action = glob.PROJECT.action(req.args.action_id)

    obj_id, action_name = action.parse_type()

    if obj_id in robot.move_in_progress:
        raise Arcor2Exception("Robot is moving.")

    params: Dict[str, Any] = {}

    for param in action.parameters:

        if param.type == common.ActionParameter.TypeEnum.LINK:

            parsed_link = param.parse_link()
            try:
                results = PREV_RESULTS[parsed_link.action_id]
            except KeyError:
                prev_action = glob.PROJECT.action(parsed_link.action_id)
                raise Arcor2Exception(f"Action '{prev_action.name}' has to be executed first.")

            if isinstance(results, collections_abc.Iterable) and not isinstance(results, str):
                params[param.id] = results[parsed_link.output_index]
            else:
                assert parsed_link.output_index == 0
                params[param.id] = results

        elif param.type == common.ActionParameter.TypeEnum.CONSTANT:
            const = glob.PROJECT.constant(param.value)
            # TODO use plugin to get the value
            import json
            params[param.id] = json.loads(const.value)
        elif param.value:

            try:
                params[param.id] = PARAM_PLUGINS[param.type].execution_value(
                    {k: v.type_def for k, v in glob.OBJECT_TYPES.items() if v.type_def is not None},
                    glob.SCENE, glob.PROJECT, action.id, param.id)
            except ParameterPluginException as e:
                await glob.logger.error(e)
                raise Arcor2Exception(f"Failed to get value for parameter {param.id}.")

    obj = get_instance(obj_id)

    if not hasattr(obj, action_name):
        raise Arcor2Exception("Internal error: object does not have the requested method.")

    glob.RUNNING_ACTION = action.id
    glob.RUNNING_ACTION_PARAMS = params

    await glob.logger.debug(f"Running action {action.name} ({type(obj)}/{action_name}), params: {params}.")

    # schedule execution and return success
    asyncio.ensure_future(execute_action(getattr(obj, action_name), params))
    return None


async def project_info(project_id: str, scenes_lock: asyncio.Lock, scenes: Dict[str, CachedScene]) -> \
        rpc.project.ListProjectsResponseData:

    project = await storage.get_project(project_id)

    assert project.modified is not None

    pd = rpc.project.ListProjectsResponseData(id=project.id, desc=project.desc, name=project.name,
                                              scene_id=project.scene_id, modified=project.modified)

    try:
        cached_project = UpdateableCachedProject(project)
    except CachedProjectException as e:
        pd.problems.append(str(e))
        return pd

    try:
        async with scenes_lock:
            if project.scene_id not in scenes:
                scenes[project.scene_id] = CachedScene(await storage.get_scene(project.scene_id))
    except storage.PersistentStorageException:
        pd.problems.append("Scene does not exist.")
        return pd

    pd.problems = project_problems(scenes[project.scene_id], cached_project)
    pd.valid = not pd.problems

    if not pd.valid:
        return pd

    # TODO for projects without logic, check if there is script uploaded in the project service /or call Build/publish
    try:
        program_src(cached_project, scenes[project.scene_id], otu.built_in_types_names())
        pd.executable = True
    except SourceException as e:
        pd.problems.append(e.message)

    return pd


async def list_projects_cb(req: rpc.project.ListProjectsRequest, ui: WsClient) -> rpc.project.ListProjectsResponse:

    projects = await storage.get_projects()

    scenes_lock = asyncio.Lock()
    scenes: Dict[str, CachedScene] = {}

    resp = rpc.project.ListProjectsResponse()
    tasks = [project_info(project_iddesc.id, scenes_lock, scenes) for project_iddesc in projects.items]
    resp.data = await asyncio.gather(*tasks)
    return resp


@scene_needed
@project_needed
async def add_action_point_joints_cb(req: rpc.project.AddActionPointJointsRequest, ui: WsClient) -> None:

    assert glob.SCENE
    assert glob.PROJECT

    ap = glob.PROJECT.action_point(req.args.action_point_id)

    unique_name(req.args.name, ap.joints_names())

    if req.dry_run:
        return None

    new_joints = await get_robot_joints(req.args.robot_id)

    prj = common.ProjectRobotJoints(common.uid(), req.args.name, req.args.robot_id, new_joints, True)
    glob.PROJECT.upsert_joints(ap.id, prj)
    asyncio.ensure_future(notif.broadcast_event(events.JointsChanged(events.EventType.ADD, ap.id, data=prj)))
    return None


@scene_needed
@project_needed
async def update_action_point_joints_cb(req: rpc.project.UpdateActionPointJointsRequest, ui: WsClient) -> None:

    assert glob.SCENE
    assert glob.PROJECT

    robot_joints = glob.PROJECT.joints(req.args.joints_id)
    new_joints = await get_robot_joints(req.args.robot_id)
    robot_joints.joints = new_joints
    robot_joints.robot_id = req.args.robot_id
    robot_joints.is_valid = True

    glob.PROJECT.update_modified()
    asyncio.ensure_future(notif.broadcast_event(events.JointsChanged(events.EventType.UPDATE, data=robot_joints)))
    return None


@scene_needed
@project_needed
async def remove_action_point_joints_cb(req: rpc.project.RemoveActionPointJointsRequest, ui: WsClient) -> None:
    """
    Removes joints from action point.
    :param req:
    :return:
    """

    assert glob.SCENE
    assert glob.PROJECT

    for act in glob.PROJECT.actions:
        for param in act.parameters:
            if PARAM_PLUGINS[param.type].uses_robot_joints(glob.PROJECT, act.id, param.id, req.args.joints_id):
                raise Arcor2Exception(f"Joints used in action {act.name} (parameter {param.id}).")

    joints_to_be_removed = glob.PROJECT.remove_joints(req.args.joints_id)

    glob.PROJECT.update_modified()
    asyncio.ensure_future(notif.broadcast_event(events.JointsChanged(events.EventType.REMOVE,
                                                                     data=joints_to_be_removed)))
    return None


@scene_needed
@project_needed
async def rename_action_point_cb(req: rpc.project.RenameActionPointRequest, ui: WsClient) -> None:

    assert glob.SCENE
    assert glob.PROJECT

    ap = glob.PROJECT.action_point(req.args.action_point_id)

    if req.args.new_name == ap.name:
        return None

    if not hlp.is_valid_identifier(req.args.new_name):
        raise Arcor2Exception("Name has to be valid Python identifier.")

    unique_name(req.args.new_name, glob.PROJECT.action_points_names)

    if req.dry_run:
        return None

    ap.name = req.args.new_name

    glob.PROJECT.update_modified()
    asyncio.ensure_future(notif.broadcast_event(events.ActionPointChanged(events.EventType.UPDATE_BASE,
                                                                          data=ap.bare())))
    return None


@scene_needed
@project_needed
async def update_action_point_parent_cb(req: rpc.project.UpdateActionPointParentRequest, ui: WsClient) -> None:

    assert glob.SCENE
    assert glob.PROJECT

    ap = glob.PROJECT.action_point(req.args.action_point_id)

    if req.args.new_parent_id == ap.parent:
        return None

    check_ap_parent(req.args.new_parent_id)

    if req.dry_run:
        return

    if not ap.parent and req.args.new_parent_id:
        # AP position and all orientations will become relative to the parent
        tr.make_global_ap_relative(glob.SCENE, glob.PROJECT, ap, req.args.new_parent_id)

    elif ap.parent and not req.args.new_parent_id:
        # AP position and all orientations will become absolute
        tr.make_relative_ap_global(glob.SCENE, glob.PROJECT, ap)
    else:

        assert ap.parent

        # AP position and all orientations will become relative to another parent
        tr.make_relative_ap_global(glob.SCENE, glob.PROJECT, ap)
        tr.make_global_ap_relative(glob.SCENE, glob.PROJECT, ap, req.args.new_parent_id)

    ap.parent = req.args.new_parent_id
    glob.PROJECT.update_modified()

    """
    Can't send orientation changes and then ActionPointChanged/UPDATE_BASE (or vice versa)
    because UI would display orientations wrongly (for a short moment).
    """
    asyncio.ensure_future(notif.broadcast_event(events.ActionPointChanged(events.EventType.UPDATE,
                                                                          data=ap)))
    return None


@scene_needed
@project_needed
async def update_action_point_position_cb(req: rpc.project.UpdateActionPointPositionRequest, ui: WsClient) -> None:

    assert glob.SCENE
    assert glob.PROJECT

    ap = glob.PROJECT.action_point(req.args.action_point_id)

    ap.position = req.args.new_position
    ap.invalidate_joints()
    for joints in ap.robot_joints:
        asyncio.ensure_future(
            notif.broadcast_event(events.JointsChanged(events.EventType.UPDATE, ap.id, data=joints)))

    glob.PROJECT.update_modified()
    asyncio.ensure_future(notif.broadcast_event(events.ActionPointChanged(events.EventType.UPDATE_BASE,
                                                                          data=ap.bare())))
    return None


@scene_needed
@project_needed
async def update_action_point_using_robot_cb(req: rpc.project.UpdateActionPointUsingRobotRequest, ui: WsClient) -> None:

    assert glob.SCENE
    assert glob.PROJECT

    ap = glob.PROJECT.action_point(req.args.action_point_id)
    new_pose = await get_end_effector_pose(req.args.robot.robot_id, req.args.robot.end_effector)

    if ap.parent:
        new_pose = tr.make_pose_rel_to_parent(glob.SCENE, glob.PROJECT, new_pose, ap.parent)

    ap.invalidate_joints()
    for joints in ap.robot_joints:
        asyncio.ensure_future(
            notif.broadcast_event(events.JointsChanged(events.EventType.UPDATE, ap.id, data=joints)))

    ap.position = new_pose.position

    glob.PROJECT.update_modified()

    asyncio.ensure_future(notif.broadcast_event(events.ActionPointChanged(events.EventType.UPDATE_BASE,
                                                                          data=ap.bare())))
    return None


@scene_needed
@project_needed
async def add_action_point_orientation_cb(req: rpc.project.AddActionPointOrientationRequest, ui: WsClient) -> None:
    """
    Adds orientation and joints to the action point.
    :param req:
    :return:
    """

    assert glob.SCENE
    assert glob.PROJECT

    ap = glob.PROJECT.action_point(req.args.action_point_id)

    unique_name(req.args.name, ap.orientation_names())

    if req.dry_run:
        return None

    orientation = common.NamedOrientation(common.uid(), req.args.name, req.args.orientation)
    glob.PROJECT.upsert_orientation(ap.id, orientation)
    asyncio.ensure_future(notif.broadcast_event(events.OrientationChanged(events.EventType.ADD, ap.id,
                                                                          data=orientation)))
    return None


@scene_needed
@project_needed
async def update_action_point_orientation_cb(req: rpc.project.UpdateActionPointOrientationRequest, ui: WsClient) -> \
        None:
    """
    Updates orientation of the action point.
    :param req:
    :return:
    """

    assert glob.SCENE
    assert glob.PROJECT

    orientation = glob.PROJECT.orientation(req.args.orientation_id)
    orientation.orientation = req.args.orientation

    glob.PROJECT.update_modified()
    asyncio.ensure_future(notif.broadcast_event(events.OrientationChanged(events.EventType.UPDATE, data=orientation)))
    return None


@scene_needed
@project_needed
async def add_action_point_orientation_using_robot_cb(req: rpc.project.AddActionPointOrientationUsingRobotRequest,
                                                      ui: WsClient) -> None:
    """
    Adds orientation and joints to the action point.
    :param req:
    :return:
    """

    assert glob.SCENE
    assert glob.PROJECT

    ap = glob.PROJECT.action_point(req.args.action_point_id)
    unique_name(req.args.name, ap.orientation_names())

    if req.dry_run:
        return None

    new_pose = await get_end_effector_pose(req.args.robot.robot_id, req.args.robot.end_effector)

    if ap.parent:
        new_pose = tr.make_pose_rel_to_parent(glob.SCENE, glob.PROJECT, new_pose, ap.parent)

    orientation = common.NamedOrientation(common.uid(), req.args.name, new_pose.orientation)
    glob.PROJECT.upsert_orientation(ap.id, orientation)
    asyncio.ensure_future(notif.broadcast_event(events.OrientationChanged(events.EventType.ADD, ap.id,
                                                                          data=orientation)))
    return None


@scene_needed
@project_needed
async def update_action_point_orientation_using_robot_cb(
        req: rpc.project.UpdateActionPointOrientationUsingRobotRequest, ui: WsClient) -> None:
    """
    Updates orientation and joint of the action point.
    :param req:
    :return:
    """

    assert glob.SCENE
    assert glob.PROJECT

    ap = glob.PROJECT.action_point(req.args.action_point_id)
    new_pose = await get_end_effector_pose(req.args.robot.robot_id, req.args.robot.end_effector)

    if ap.parent:
        new_pose = tr.make_pose_rel_to_parent(glob.SCENE, glob.PROJECT, new_pose, ap.parent)

    ori = glob.PROJECT.orientation(req.args.orientation_id)
    ori.orientation = new_pose.orientation

    glob.PROJECT.update_modified()
    asyncio.ensure_future(notif.broadcast_event(events.OrientationChanged(events.EventType.UPDATE, data=ori)))
    return None


@scene_needed
@project_needed
async def remove_action_point_orientation_cb(req: rpc.project.RemoveActionPointOrientationRequest, ui: WsClient) -> \
        None:
    """
    Removes orientation.
    :param req:
    :return:
    """

    assert glob.SCENE
    assert glob.PROJECT

    ap, orientation = glob.PROJECT.ap_and_orientation(req.args.action_point_id)

    for act in glob.PROJECT.actions:
        for param in act.parameters:
            if PARAM_PLUGINS[param.type].uses_orientation(glob.PROJECT, act.id, param.id, req.args.orientation_id):
                raise Arcor2Exception(f"Orientation used in action {act.name} (parameter {param.id}).")

    if req.dry_run:
        return None

    glob.PROJECT.remove_orientation(req.args.orientation_id)
    asyncio.ensure_future(notif.broadcast_event(events.OrientationChanged(events.EventType.REMOVE, data=orientation)))
    return None


async def open_project_cb(req: rpc.project.OpenProjectRequest, ui: WsClient) -> None:

    if glob.PACKAGE_STATE.state in (common.PackageStateEnum.PAUSED, common.PackageStateEnum.RUNNING):
        raise Arcor2Exception("Can't open project while package runs.")

    # TODO validate using project_problems?
    await open_project(req.args.id)

    assert glob.SCENE
    assert glob.PROJECT

    asyncio.ensure_future(notif.broadcast_event(events.OpenProject(data=events.OpenProjectData(glob.SCENE.scene,
                                                                                               glob.PROJECT.project))))

    return None


@scene_needed
@project_needed
async def save_project_cb(req: rpc.project.SaveProjectRequest, ui: WsClient) -> None:

    assert glob.SCENE
    assert glob.PROJECT

    await storage.update_project(glob.PROJECT.project)
    # TODO get modified from response
    glob.PROJECT.modified = (await storage.get_project(glob.PROJECT.id)).modified
    asyncio.ensure_future(notif.broadcast_event(events.ProjectSaved()))
    return None


@no_project
async def new_project_cb(req: rpc.project.NewProjectRequest, ui: WsClient) -> None:

    if glob.PACKAGE_STATE.state in (common.PackageStateEnum.PAUSED, common.PackageStateEnum.RUNNING):
        raise Arcor2Exception("Can't create project while package runs.")

    unique_name(req.args.name, (await project_names()))

    if req.dry_run:
        return None

    if glob.SCENE:
        if glob.SCENE.id != req.args.scene_id:
            raise Arcor2Exception("Another scene is opened.")

        if glob.SCENE.has_changes():
            await storage.update_scene(glob.SCENE.scene)
            glob.SCENE.modified = (await storage.get_scene(glob.SCENE.id)).modified

    else:

        if req.args.scene_id not in {scene.id for scene in (await storage.get_scenes()).items}:
            raise Arcor2Exception("Unknown scene id.")

        await open_scene(req.args.scene_id)

    PREV_RESULTS.clear()
    glob.PROJECT = UpdateableCachedProject(
        common.Project(common.uid(), req.args.name, req.args.scene_id, desc=req.args.desc, has_logic=req.args.has_logic)
    )

    assert glob.SCENE

    asyncio.ensure_future(notif.broadcast_event(events.OpenProject(data=events.OpenProjectData(glob.SCENE.scene,
                                                                                               glob.PROJECT.project))))
    return None


async def notify_project_closed(project_id: str) -> None:

    await notif.broadcast_event(events.ProjectClosed())
    glob.MAIN_SCREEN = events.ShowMainScreenData(events.ShowMainScreenData.WhatEnum.ProjectsList)
    await notif.broadcast_event(events.ShowMainScreenEvent(
        data=events.ShowMainScreenData(events.ShowMainScreenData.WhatEnum.ProjectsList, project_id)))


@scene_needed
@project_needed
async def close_project_cb(req: rpc.project.CloseProjectRequest, ui: WsClient) -> None:

    assert glob.PROJECT

    if not req.args.force and glob.PROJECT.has_changes:
        raise Arcor2Exception("Project has unsaved changes.")

    if req.dry_run:
        return None

    project_id = glob.PROJECT.project.id

    glob.PROJECT = None
    await clear_scene()
    PREV_RESULTS.clear()
    asyncio.ensure_future(notify_project_closed(project_id))

    return None


def check_ap_parent(parent: Optional[str]) -> None:

    assert glob.SCENE
    assert glob.PROJECT

    if not parent:
        return

    if parent in glob.SCENE.object_ids:
        if glob.SCENE.object(parent).pose is None:
            raise Arcor2Exception("AP can't have object without pose as parent.")
    elif parent not in glob.PROJECT.action_points_ids:
        raise Arcor2Exception("AP has invalid parent ID (not an object or another AP).")


@scene_needed
@project_needed
async def add_action_point_cb(req: rpc.project.AddActionPointRequest, ui: WsClient) -> None:

    assert glob.SCENE
    assert glob.PROJECT

    unique_name(req.args.name, glob.PROJECT.action_points_names)
    check_ap_parent(req.args.parent)

    if not hlp.is_valid_identifier(req.args.name):
        raise Arcor2Exception("Name has to be valid Python identifier.")

    if req.dry_run:
        return None

    ap = glob.PROJECT.upsert_action_point(common.uid(), req.args.name, req.args.position, req.args.parent)
    asyncio.ensure_future(notif.broadcast_event(events.ActionPointChanged(events.EventType.ADD, data=ap)))
    return None


@scene_needed
@project_needed
async def remove_action_point_cb(req: rpc.project.RemoveActionPointRequest, ui: WsClient) -> None:

    assert glob.PROJECT

    ap = glob.PROJECT.action_point(req.args.id)

    for proj_ap in glob.PROJECT.action_points_with_parent:
        if proj_ap.parent == ap.id:
            raise Arcor2Exception(f"Can't remove parent of '{proj_ap.name}' AP.")

    ap_action_ids = ap.action_ids()

    # check if AP's actions aren't involved in logic
    # TODO 'force' param to remove logical connections?
    for logic in glob.PROJECT.logic:
        if logic.start in ap_action_ids or logic.end in ap_action_ids or \
                (logic.condition and logic.condition.parse_what().action_id in ap_action_ids):
            raise Arcor2Exception("Remove logic connections first.")

    for act in glob.PROJECT.actions:

        if act.id in ap_action_ids:
            continue

        for param in act.parameters:
            if param.type == common.ActionParameter.TypeEnum.LINK:
                parsed_link = param.parse_link()
                linking_action = glob.PROJECT.action(parsed_link.action_id)
                if parsed_link.action_id in ap_action_ids:
                    raise Arcor2Exception(f"Result of '{act.name}' is linked from '{linking_action.name}'.")

            if not param.is_value():
                continue

            for joints in ap.robot_joints:
                if PARAM_PLUGINS[param.type].uses_robot_joints(glob.PROJECT, act.id, param.id, joints.id):
                    raise Arcor2Exception(f"Joints {joints.name} used in action {act.name} (parameter {param.id}).")

            for ori in ap.orientations:
                if PARAM_PLUGINS[param.type].uses_orientation(glob.PROJECT, act.id, param.id, ori.id):
                    raise Arcor2Exception(f"Orientation {ori.name} used in action {act.name} (parameter {param.id}).")

            # TODO some hypothetical parameter type could use just bare ActionPoint (its position)

    if req.dry_run:
        return None

    glob.PROJECT.remove_action_point(req.args.id)
    asyncio.ensure_future(notif.broadcast_event(events.ActionPointChanged(events.EventType.REMOVE, data=ap.bare())))
    return None


@scene_needed
@project_needed
async def add_action_cb(req: rpc.project.AddActionRequest, ui: WsClient) -> None:

    assert glob.PROJECT
    assert glob.SCENE

    ap = glob.PROJECT.action_point(req.args.action_point_id)

    unique_name(req.args.name, glob.PROJECT.action_user_names())

    if not hlp.is_valid_identifier(req.args.name):
        raise Arcor2Exception("Action name has to be valid Python identifier.")

    new_action = common.Action(common.uid(), req.args.name, req.args.type, req.args.parameters, req.args.flows)

    action_meta = find_object_action(glob.SCENE, new_action)

    updated_project = copy.deepcopy(glob.PROJECT)
    updated_project.upsert_action(req.args.action_point_id, new_action)

    check_flows(updated_project, new_action, action_meta)
    check_action_params(glob.SCENE, updated_project, new_action, action_meta)

    if req.dry_run:
        return None

    glob.PROJECT.upsert_action(ap.id, new_action)
    asyncio.ensure_future(notif.broadcast_event(events.ActionChanged(events.EventType.ADD, ap.id, data=new_action)))
    return None


@scene_needed
@project_needed
async def update_action_cb(req: rpc.project.UpdateActionRequest, ui: WsClient) -> None:

    assert glob.PROJECT
    assert glob.SCENE

    updated_project = copy.deepcopy(glob.PROJECT)

    updated_action = updated_project.action(req.args.action_id)

    if req.args.parameters is not None:
        updated_action.parameters = req.args.parameters
    if req.args.flows is not None:
        updated_action.flows = req.args.flows

    updated_action_meta = find_object_action(glob.SCENE, updated_action)

    check_flows(updated_project, updated_action, updated_action_meta)
    check_action_params(glob.SCENE, updated_project, updated_action, updated_action_meta)

    if req.dry_run:
        return None

    orig_action = glob.PROJECT.action(req.args.action_id)
    orig_action.parameters = updated_action.parameters
    glob.PROJECT.update_modified()

    asyncio.ensure_future(notif.broadcast_event(events.ActionChanged(events.EventType.UPDATE,
                                                                     data=updated_action)))
    return None


def check_action_usage(action: common.Action) -> None:

    assert glob.PROJECT

    # check parameters
    for act in glob.PROJECT.actions:
        for param in act.parameters:
            if param.type == common.ActionParameter.TypeEnum.LINK:
                link = param.parse_link()
                if action.id == link.action_id:
                    raise Arcor2Exception(f"Action output used as parameter of {act.name}/{param.id}.")

    # check logic
    for log in glob.PROJECT.logic:

        if log.start == action.id or log.end == action.id:
            raise Arcor2Exception("Action used in logic.")

        if log.condition:
            action_id, _, _ = log.condition.what.split("/")

            if action_id == action.id:
                raise Arcor2Exception("Action used in condition.")


@scene_needed
@project_needed
async def remove_action_cb(req: rpc.project.RemoveActionRequest, ui: WsClient) -> None:

    assert glob.PROJECT
    assert glob.SCENE

    ap, action = glob.PROJECT.action_point_and_action(req.args.id)
    check_action_usage(action)

    if req.dry_run:
        return None

    glob.PROJECT.remove_action(req.args.id)
    remove_prev_result(action.id)

    asyncio.ensure_future(notif.broadcast_event(events.ActionChanged(events.EventType.REMOVE, data=action.bare)))
    return None


def check_logic_item(parent: LogicContainer, logic_item: common.LogicItem) -> None:
    """
    Checks if newly added/updated ProjectLogicItem is ok.
    :param parent:
    :param logic_item:
    :return:
    """

    assert glob.SCENE

    action_ids = parent.action_ids()

    if logic_item.start == common.LogicItem.START and logic_item.end == common.LogicItem.END:
        raise Arcor2Exception("This does not make sense.")

    if logic_item.start != common.LogicItem.START:

        start_action_id, start_flow = logic_item.parse_start()

        if start_action_id == logic_item.end:
            raise Arcor2Exception("Start and end can't be the same.")

        if start_action_id not in action_ids:
            raise Arcor2Exception("Logic item has unknown start.")

        if start_flow != "default":
            raise Arcor2Exception("Only flow 'default' is supported so far.'")

    if logic_item.end != common.LogicItem.END:

        if logic_item.end not in action_ids:
            raise Arcor2Exception("Logic item has unknown end.")

    if logic_item.condition is not None:
        # what = logic_item.condition.parse_what()
        # action = parent.action(what.action_id)
        # flow = action.flow(what.flow_name)
        # obj_act = find_object_action(glob.SCENE, action)

        # TODO check if flow is valid
        # TODO check condition value / type

        pass

    for existing_item in parent.logic:

        if existing_item.id == logic_item.id:  # item is updated
            continue

        if logic_item.start == logic_item.START and existing_item.start == logic_item.START:
            raise Arcor2Exception("START already defined.")

        if logic_item.start == existing_item.start:

            if None in (logic_item.condition, existing_item.condition):
                raise Arcor2Exception("Two junctions has the same start action without condition.")

            if logic_item.condition == existing_item.condition:
                raise Arcor2Exception("Two junctions with the same start should have different conditions.")

        if logic_item.end == existing_item.end:
            if logic_item.start == existing_item.start:
                raise Arcor2Exception("Junctions can't have the same start and end.")


@scene_needed
@project_needed
async def add_logic_item_cb(req: rpc.project.AddLogicItemRequest, ui: WsClient) -> None:

    assert glob.PROJECT
    assert glob.SCENE

    logic_item = common.LogicItem(common.uid(), req.args.start, req.args.end, req.args.condition)
    check_logic_item(glob.PROJECT, logic_item)

    if logic_item.start != logic_item.START:
        updated_project = copy.deepcopy(glob.PROJECT)
        updated_project.upsert_logic_item(logic_item)
        check_for_loops(updated_project, logic_item.parse_start().start_action_id)

    if req.dry_run:
        return

    glob.PROJECT.upsert_logic_item(logic_item)
    asyncio.ensure_future(notif.broadcast_event(events.LogicItemChanged(events.EventType.ADD, data=logic_item)))
    return None


@scene_needed
@project_needed
async def update_logic_item_cb(req: rpc.project.UpdateLogicItemRequest, ui: WsClient) -> None:

    assert glob.PROJECT
    assert glob.SCENE

    updated_project = copy.deepcopy(glob.PROJECT)
    updated_logic_item = updated_project.logic_item(req.args.logic_item_id)

    updated_logic_item.start = req.args.start
    updated_logic_item.end = req.args.end
    updated_logic_item.condition = req.args.condition

    check_logic_item(updated_project, updated_logic_item)

    if updated_logic_item.start != updated_logic_item.START:
        check_for_loops(updated_project, updated_logic_item.parse_start().start_action_id)

    if req.dry_run:
        return

    glob.PROJECT.upsert_logic_item(updated_logic_item)
    asyncio.ensure_future(notif.broadcast_event(events.LogicItemChanged(events.EventType.UPDATE,
                                                                        data=updated_logic_item)))
    return None


@scene_needed
@project_needed
async def remove_logic_item_cb(req: rpc.project.RemoveLogicItemRequest, ui: WsClient) -> None:

    assert glob.PROJECT
    assert glob.SCENE

    logic_item = glob.PROJECT.logic_item(req.args.logic_item_id)

    # TODO is it necessary to check something here?
    glob.PROJECT.remove_logic_item(req.args.logic_item_id)
    asyncio.ensure_future(notif.broadcast_event(events.LogicItemChanged(events.EventType.REMOVE, data=logic_item)))
    return None


def check_constant(constant: common.ProjectConstant) -> None:

    assert glob.PROJECT

    if not hlp.is_valid_identifier(constant.name):
        raise Arcor2Exception("Name has to be valid Python identifier.")

    for const in glob.PROJECT.constants:

        if constant.id == const.id:
            continue

        if constant.name == const.name:
            raise Arcor2Exception("Name has to be unique.")

    # TODO check using (constant?) plugin


@scene_needed
@project_needed
async def add_constant_cb(req: rpc.project.AddConstantRequest, ui: WsClient) -> None:

    assert glob.PROJECT
    assert glob.SCENE

    const = common.ProjectConstant(common.uid(), req.args.name, req.args.type, req.args.value)
    check_constant(const)

    if req.dry_run:
        return

    glob.PROJECT.upsert_constant(const)
    asyncio.ensure_future(notif.broadcast_event(events.ProjectConstantChanged(events.EventType.ADD, data=const)))
    return None


@scene_needed
@project_needed
async def update_constant_cb(req: rpc.project.UpdateConstantRequest, ui: WsClient) -> None:

    assert glob.PROJECT
    assert glob.SCENE

    const = glob.PROJECT.constant(req.args.constant_id)

    updated_constant = copy.deepcopy(const)

    if req.args.name is not None:
        updated_constant.name = req.args.name
    if req.args.value is not None:
        updated_constant.value = req.args.value

    check_constant(const)

    if req.dry_run:
        return

    glob.PROJECT.upsert_constant(updated_constant)
    asyncio.ensure_future(notif.broadcast_event(events.ProjectConstantChanged(events.EventType.UPDATE, data=const)))
    return None


@scene_needed
@project_needed
async def remove_constant_cb(req: rpc.project.RemoveConstantRequest, ui: WsClient) -> None:

    assert glob.PROJECT
    assert glob.SCENE

    const = glob.PROJECT.constant(req.args.constant_id)

    # check for usage
    for ap in glob.PROJECT.action_points:
        for act in ap.actions:
            for param in act.parameters:
                if param.type == common.ActionParameter.TypeEnum.CONSTANT and param.value == const.id:
                    raise Arcor2Exception("Constant used as action parameter.")

    if req.dry_run:
        return

    glob.PROJECT.remove_constant(const.id)
    asyncio.ensure_future(notif.broadcast_event(events.ProjectConstantChanged(events.EventType.REMOVE, data=const)))
    return None


@no_project
async def delete_project_cb(req: rpc.project.DeleteProjectRequest, ui: WsClient) -> None:

    project = UpdateableCachedProject(await storage.get_project(req.args.id))
    await storage.delete_project(req.args.id)
    asyncio.ensure_future(notif.broadcast_event(events.ProjectChanged(events.EventType.REMOVE,
                                                                      data=project.bare)))
    return None


async def rename_project_cb(req: rpc.project.RenameProjectRequest, ui: WsClient) -> None:

    unique_name(req.args.new_name, (await project_names()))

    if req.dry_run:
        return None

    async with managed_project(req.args.project_id) as project:

        project.name = req.args.new_name
        project.update_modified()

        asyncio.ensure_future(notif.broadcast_event(events.ProjectChanged(events.EventType.UPDATE_BASE,
                                                                          data=project.bare)))
    return None


async def copy_project_cb(req: rpc.project.CopyProjectRequest, ui: WsClient) -> None:

    unique_name(req.args.target_name, (await project_names()))

    if req.dry_run:
        return None

    async with managed_project(req.args.source_id, make_copy=True) as project:

        project.name = req.args.target_name
        asyncio.ensure_future(notif.broadcast_event(events.ProjectChanged(events.EventType.UPDATE_BASE,
                                                                          data=project.bare)))

    return None


async def update_project_description_cb(req: rpc.project.UpdateProjectDescriptionRequest, ui: WsClient) -> None:

    async with managed_project(req.args.project_id) as project:

        project.desc = req.args.new_description
        project.update_modified()

        asyncio.ensure_future(notif.broadcast_event(events.ProjectChanged(events.EventType.UPDATE_BASE,
                                                                          data=project.bare)))
    return None


async def update_project_has_logic_cb(req: rpc.project.UpdateProjectHasLogicRequest, ui: WsClient) -> None:

    async with managed_project(req.args.project_id) as project:

        if project.has_logic and not req.args.new_has_logic:
            project.clear_logic()

            """
            TODO
            if glob.PROJECT and glob.PROJECT.id == req.args.project_id:
            ...send remove event for each logic item?
            """

        project.has_logic = req.args.new_has_logic
        project.update_modified()
        asyncio.ensure_future(notif.broadcast_event(events.ProjectChanged(events.EventType.UPDATE_BASE,
                                                                          data=project.bare)))
    return None


@project_needed
async def rename_action_point_joints_cb(req: rpc.project.RenameActionPointJointsRequest, ui: WsClient) -> None:

    assert glob.PROJECT

    ap, joints = glob.PROJECT.ap_and_joints(req.args.joints_id)
    unique_name(req.args.new_name, ap.joints_names())

    if req.dry_run:
        return None

    joints.name = req.args.new_name
    glob.PROJECT.update_modified()
    asyncio.ensure_future(notif.broadcast_event(events.JointsChanged(events.EventType.UPDATE_BASE, data=joints)))

    return None


@project_needed
async def rename_action_point_orientation_cb(req: rpc.project.RenameActionPointOrientationRequest, ui: WsClient) -> \
        None:

    assert glob.PROJECT

    ap, ori = glob.PROJECT.ap_and_orientation(req.args.orientation_id)
    unique_name(req.args.new_name, ap.orientation_names())

    if req.dry_run:
        return None

    ori.name = req.args.new_name
    glob.PROJECT.update_modified()
    asyncio.ensure_future(notif.broadcast_event(events.OrientationChanged(events.EventType.UPDATE_BASE, data=ori)))

    return None


@project_needed
async def rename_action_cb(req: rpc.project.RenameActionRequest, ui: WsClient) -> None:

    assert glob.PROJECT

    unique_name(req.args.new_name, glob.PROJECT.action_user_names())

    if req.dry_run:
        return None

    act = glob.PROJECT.action(req.args.action_id)
    act.name = req.args.new_name

    glob.PROJECT.update_modified()
    asyncio.ensure_future(notif.broadcast_event(events.ActionChanged(events.EventType.UPDATE_BASE, data=act)))

    return None
