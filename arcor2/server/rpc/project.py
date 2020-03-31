#!/usr/bin/env python3
# -*- coding: utf-8 -*-


import asyncio
from typing import Union, List, Dict, Any, Optional
import uuid

from arcor2 import object_types_utils as otu, helpers as hlp
from arcor2.data.common import Scene, ProjectRobotJoints, NamedOrientation, Project, ProjectActionPoint, Action
from arcor2.data import rpc, events
from arcor2 import aio_persistent_storage as storage
from arcor2.object_types import Generic
from arcor2.services import Service
from arcor2.exceptions import Arcor2Exception
from arcor2.parameter_plugins import PARAM_PLUGINS
from arcor2.parameter_plugins.base import ParameterPluginException
from arcor2.source.logic import program_src, SourceException

from arcor2.server.decorators import scene_needed, project_needed, no_project
from arcor2.server import objects_services_actions as osa, notifications as notif, globals as glob
from arcor2.server.robot import get_end_effector_pose, get_robot_joints, RobotPoseException
from arcor2.server.project import project_problems, open_project


@scene_needed
@project_needed
async def execute_action_cb(req: rpc.project.ExecuteActionRequest) -> \
        Union[rpc.project.ExecuteActionResponse, hlp.RPC_RETURN_TYPES]:

    assert glob.SCENE and glob.PROJECT

    if glob.RUNNING_ACTION:
        return False, f"Action {glob.RUNNING_ACTION} is being executed. Only one action can be executed at a time."

    try:
        action = glob.PROJECT.action(req.args.action_id)
    except Arcor2Exception:
        return False, "Unknown action."

    params: Dict[str, Any] = {}

    for param in action.parameters:
        try:
            params[param.id] = PARAM_PLUGINS[param.type].value(glob.TYPE_DEF_DICT, glob.SCENE,
                                                               glob.PROJECT, action.id, param.id)
        except ParameterPluginException as e:
            await glob.logger.error(e)
            return False, f"Failed to get value for parameter {param.id}."

    obj_id, action_name = action.parse_type()

    obj: Optional[Union[Generic, Service]] = None

    if obj_id in glob.SCENE_OBJECT_INSTANCES:
        obj = glob.SCENE_OBJECT_INSTANCES[obj_id]
    elif obj_id in glob.SERVICES_INSTANCES:
        obj = glob.SERVICES_INSTANCES[obj_id]
    else:
        return False, "Internal error: project not in sync with scene."

    if not hasattr(obj, action_name):
        return False, "Internal error: object does not have the requested method."

    glob.RUNNING_ACTION = action.id

    # schedule execution and return success
    asyncio.ensure_future(osa.execute_action(getattr(obj, action_name), params))
    return None


async def list_projects_cb(req: rpc.project.ListProjectsRequest) -> \
        Union[rpc.project.ListProjectsResponse, hlp.RPC_RETURN_TYPES]:

    data: List[rpc.project.ListProjectsResponseData] = []

    projects = await storage.get_projects()

    scenes: Dict[str, Scene] = {}

    for project_iddesc in projects.items:

        try:
            project = await storage.get_project(project_iddesc.id)
        except Arcor2Exception as e:
            await glob.logger.warning(f"Ignoring project {project_iddesc.id} due to error: {e}")
            continue

        pd = rpc.project.ListProjectsResponseData(id=project.id, desc=project.desc)
        data.append(pd)

        if project.scene_id not in scenes:
            try:
                scenes[project.scene_id] = await storage.get_scene(project.scene_id)
            except storage.PersistentStorageException:
                pd.problems.append("Scene does not exist.")
                continue

        pd.problems = project_problems(scenes[project.scene_id], project)
        pd.valid = not pd.problems

        if not pd.valid:
            continue

        try:
            program_src(project, scenes[project.scene_id], otu.built_in_types_names())
            pd.executable = True
        except SourceException as e:
            pd.problems.append(str(e))

    return rpc.project.ListProjectsResponse(data=data)


@scene_needed
@project_needed
async def add_ap_joints_cb(req: rpc.project.AddActionPointJointsRequest) -> \
        Union[rpc.project.AddActionPointJointsResponse, hlp.RPC_RETURN_TYPES]:

    assert glob.SCENE and glob.PROJECT

    try:
        ap = glob.PROJECT.action_point(req.args.action_point_id)
    except Arcor2Exception:
        return False, "Invalid action point."

    for joints in ap.robot_joints:
        if req.args.user_id == joints.user_id:
            return False, "User id already exists."

    try:
        new_joints = await get_robot_joints(req.args.robot_id)
    except Arcor2Exception as e:
        return False, str(e)

    prj = ProjectRobotJoints(uuid.uuid4().hex, req.args.user_id, req.args.robot_id, new_joints, True)
    ap.robot_joints.append(prj)
    asyncio.ensure_future(notif.broadcast_event(events.ActionPointChanged(events.EventType.UPDATE, ap)))
    return None


@scene_needed
@project_needed
async def update_ap_joints_cb(req: rpc.objects.UpdateActionPointJointsRequest) -> \
        Union[rpc.objects.UpdateActionPointJointsResponse, hlp.RPC_RETURN_TYPES]:

    assert glob.SCENE and glob.PROJECT

    try:
        ap = glob.PROJECT.action_point(req.args.id)
    except Arcor2Exception:
        return False, "Invalid action point."

    for orientation in ap.orientations:
        if orientation.id == req.args.joints_id:
            return False, "Can't update joints that are paired with orientation."

    for joint in ap.robot_joints:  # update existing joints_id
        if joint.id == req.args.joints_id:
            robot_joints = joint
            break
    else:
        return False, "Joints were not found."

    try:
        new_joints = await get_robot_joints(req.args.robot_id)
    except Arcor2Exception as e:
        return False, str(e)

    robot_joints.joints = new_joints
    robot_joints.robot_id = req.args.robot_id
    robot_joints.is_valid = True

    asyncio.ensure_future(notif.broadcast_event(events.ActionPointChanged(events.EventType.UPDATE, ap)))
    return None


@scene_needed
@project_needed
async def update_action_point_cb(req: rpc.project.UpdateActionPointRequest) -> \
        Union[rpc.project.UpdateActionPointResponse, hlp.RPC_RETURN_TYPES]:

    assert glob.SCENE and glob.PROJECT

    ap = glob.PROJECT.action_point(req.args.action_point_id)

    change = False

    if req.args.new_user_id is not None:

        if not hlp.is_valid_identifier(req.args.new_user_id):
            return False, "User id is not a valid Python identifier."

        if req.args.new_user_id in glob.PROJECT.action_points_user_ids:
            return False, "User id is not unique."

        ap.user_id = req.args.new_user_id
        change = True

    if req.args.new_parent_id is not None:

        if req.args.new_parent_id:

            try:
                glob.SCENE.object(req.args.new_parent_id)
            except Arcor2Exception:
                return False, "Unknown parent ID."

        ap.parent = req.args.new_parent_id
        ap.invalidate_joints()
        change = True

    if req.args.new_position is not None:

        ap.position = req.args.new_position
        ap.invalidate_joints()
        change = True

    if not change:
        return False, "No change requested."

    asyncio.ensure_future(notif.broadcast_event(events.ActionPointChanged(events.EventType.UPDATE, ap)))
    return None


@scene_needed
@project_needed
async def add_action_point_orientation_cb(req: rpc.project.AddActionPointOrientationRequest) -> \
        Union[rpc.project.AddActionPointOrientationResponse, hlp.RPC_RETURN_TYPES]:

    assert glob.SCENE and glob.PROJECT

    try:
        ap = glob.PROJECT.action_point(req.args.action_point_id)
    except Arcor2Exception:
        return False, "Invalid action point."

    for ori in ap.orientations:
        if ori.user_id == req.args.user_id:
            return False, "Orientation with desired user id already exists."

    for joints in ap.robot_joints:
        if joints.user_id == req.args.user_id:
            return False, "Joints with desired user id already exist."

    try:
        new_pose, new_joints = await asyncio.gather(get_end_effector_pose(req.args.robot.robot_id,
                                                                          req.args.robot.end_effector),
                                                    get_robot_joints(req.args.robot.robot_id))
    except RobotPoseException as e:
        return False, str(e)

    if ap.parent:
        obj = glob.SCENE_OBJECT_INSTANCES[ap.parent]
        new_pose = hlp.make_pose_rel(obj.pose, new_pose)

    ap.orientations.append(NamedOrientation(uuid.uuid4().hex, req.args.user_id, new_pose.orientation))
    ap.robot_joints.append(
        ProjectRobotJoints(uuid.uuid4().hex, req.args.user_id, req.args.robot.robot_id, new_joints))

    asyncio.ensure_future(notif.broadcast_event(events.ActionPointChanged(events.EventType.UPDATE, ap)))
    return None


@scene_needed
@project_needed
async def update_action_point_orientation_cb(req: rpc.project.UpdateActionPointOrientationRequest) -> \
        Union[rpc.project.UpdateActionPointOrientationResponse, hlp.RPC_RETURN_TYPES]:

    assert glob.SCENE and glob.PROJECT

    try:
        ap = glob.PROJECT.action_point(req.args.action_point_id)
    except Arcor2Exception:
        return False, "Invalid action point."

    try:
        new_pose, new_joints = await asyncio.gather(get_end_effector_pose(req.args.robot.robot_id,
                                                                          req.args.robot.end_effector),
                                                    get_robot_joints(req.args.robot.robot_id))
    except RobotPoseException as e:
        return False, str(e)

    if ap.parent:

        obj = glob.SCENE_OBJECT_INSTANCES[ap.parent]
        new_pose = hlp.make_pose_rel(obj.pose, new_pose)

    for ori in ap.orientations:
        if ori.id == req.args.orientation_id:
            ori.orientation = new_pose.orientation
            break
    else:
        return False, "Unknown orientation."

    for joint in ap.robot_joints:
        if joint.id == req.args.orientation_id:
            joint.joints = new_joints
            joint.robot_id = req.args.robot.robot_id
            joint.is_valid = True
            break
    else:
        return False, "Unknown joints."

    asyncio.ensure_future(notif.broadcast_event(events.ActionPointChanged(events.EventType.UPDATE, ap)))
    return None


async def open_project_cb(req: rpc.project.OpenProjectRequest) -> Union[rpc.project.OpenProjectResponse,
                                                                              hlp.RPC_RETURN_TYPES]:

    # TODO validate using project_problems?
    try:
        await open_project(req.args.id)
    except Arcor2Exception as e:
        await glob.logger.exception(f"Failed to open project {req.args.id}.")
        return False, str(e)

    return None


@scene_needed
@project_needed
async def save_project_cb(req: rpc.project.SaveProjectRequest) -> Union[rpc.project.SaveProjectResponse,
                                                                              hlp.RPC_RETURN_TYPES]:

    assert glob.SCENE and glob.PROJECT
    await storage.update_project(glob.PROJECT)
    return None


@no_project
async def new_project_cb(req: rpc.project.NewProjectRequest) -> Union[rpc.project.NewProjectResponse,
                                                                      hlp.RPC_RETURN_TYPES]:

    if req.args.scene_id not in {scene.id for scene in (await storage.get_scenes()).items}:
        return False, "Unknown scene id."

    # TODO make sure that user_id of the project is not already taken?

    glob.PROJECT = Project(uuid.uuid4().hex, req.args.user_id, req.args.scene_id, desc=req.args.desc)
    asyncio.ensure_future(notif.broadcast_event(events.ProjectChangedEvent(events.EventType.ADD, glob.PROJECT)))
    return None


@scene_needed
@project_needed
async def close_project_cb(req: rpc.project.CloseProjectRequest) -> Union[rpc.project.CloseProjectResponse,
                                                                          hlp.RPC_RETURN_TYPES]:
    assert glob.PROJECT

    if not req.args.force:

        saved_project = await storage.get_project(glob.PROJECT.id)

        if saved_project.last_modified and glob.PROJECT.last_modified and \
                saved_project.last_modified < glob.PROJECT.last_modified:
            return False, "Project has unsaved changes."

    glob.PROJECT = None
    asyncio.ensure_future(notif.broadcast_event(events.ProjectChangedEvent(events.EventType.UPDATE)))
    return None


@scene_needed
@project_needed
async def add_action_point_cb(req: rpc.project.AddActionPointRequest) -> Union[rpc.project.AddActionPointResponse,
                                                                          hlp.RPC_RETURN_TYPES]:

    assert glob.PROJECT

    if req.args.user_id in glob.PROJECT.action_points_user_ids:
        return False, "Action point user id is already used."

    ap = ProjectActionPoint(uuid.uuid4().hex, req.args.user_id, req.args.position)
    glob.PROJECT.action_points.append(ap)
    asyncio.ensure_future(notif.broadcast_event(events.ActionPointChanged(events.EventType.ADD, ap)))
    return None


@scene_needed
@project_needed
async def add_action_cb(req: rpc.project.AddActionRequest) -> Union[rpc.project.AddActionResponse,
                                                                          hlp.RPC_RETURN_TYPES]:

    assert glob.PROJECT
    assert glob.SCENE

    try:
        ap = glob.PROJECT.action_point(req.args.action_point_id)
    except Arcor2Exception as e:
        return False, str(e)

    if req.args.user_id in glob.PROJECT.action_user_ids():
        return False, "Action user id already exists."

    if not hlp.is_valid_identifier(req.args.user_id):
        return False, "Action user id is not a valid Python identifier."

    action = Action(uuid.uuid4().hex, req.args.user_id, req.args.type, req.args.parameters)

    try:
        obj_id, action_type = action.parse_type()
    except Arcor2Exception as e:
        return False, str(e)

    try:
        glob.SCENE.object_or_service(obj_id)
    except Arcor2Exception as e:
        return False, str(e)

    for act in glob.ACTIONS[obj_id]:
        if action_type == act.name:
            if act.disabled:
                return False, "Action type is disabled."
            break
    else:
        return False, "Unknown action type."

    for param in req.args.parameters:
        # TODO validate parameters
        pass

    ap.actions.append(action)
    asyncio.ensure_future(notif.broadcast_event(events.ActionPointChanged(events.EventType.ADD, ap)))
    return None
