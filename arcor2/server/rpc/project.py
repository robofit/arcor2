#!/usr/bin/env python3
# -*- coding: utf-8 -*-


import asyncio
from typing import Union, List, Dict, Any, Optional

from arcor2 import object_types_utils as otu, helpers as hlp
from arcor2.data.common import Scene, ProjectRobotJoints, NamedOrientation
from arcor2.data import rpc
from arcor2 import aio_persistent_storage as storage
from arcor2.object_types import Generic
from arcor2.services import Service
from arcor2.exceptions import Arcor2Exception
from arcor2.parameter_plugins import PARAM_PLUGINS
from arcor2.parameter_plugins.base import ParameterPluginException
from arcor2.source.logic import program_src, SourceException
from arcor2.project_utils import get_object_ap, ActionPointNotFound

from arcor2.server.decorators import scene_needed, project_needed
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
async def update_ap_joints_cb(req: rpc.objects.UpdateActionPointJointsRequest) -> \
        Union[rpc.objects.UpdateActionPointJointsResponse, hlp.RPC_RETURN_TYPES]:

    assert glob.SCENE and glob.PROJECT

    try:
        proj_obj, ap = get_object_ap(glob.PROJECT, req.args.id)
    except ActionPointNotFound:
        return False, "Invalid action point."

    try:
        new_joints = await get_robot_joints(req.args.robot_id)
    except Arcor2Exception as e:
        return False, str(e)

    for orientation in ap.orientations:
        if orientation.id == req.args.joints_id:
            return False, "Can't update joints that are paired with orientation."

    for joint in ap.robot_joints:  # update existing joints_id
        if joint.id == req.args.joints_id:
            joint.joints = new_joints
            joint.robot_id = req.args.robot_id
            joint.is_valid = True
            break
    else:
        ap.robot_joints.append(ProjectRobotJoints(req.args.joints_id, req.args.robot_id, new_joints))

    asyncio.ensure_future(notif.notify_project_change_to_others())
    return None


@scene_needed
@project_needed
async def update_action_point_cb(req: rpc.objects.UpdateActionPointPoseRequest) -> \
        Union[rpc.objects.UpdateActionPointPoseResponse, hlp.RPC_RETURN_TYPES]:

    assert glob.SCENE and glob.PROJECT

    try:
        proj_obj, ap = get_object_ap(glob.PROJECT, req.args.id)
    except ActionPointNotFound:
        return False, "Invalid action point."

    try:
        new_pose, new_joints = await asyncio.gather(get_end_effector_pose(req.args.robot.robot_id,
                                                                          req.args.robot.end_effector),
                                                    get_robot_joints(req.args.robot.robot_id))
    except RobotPoseException as e:
        return False, str(e)

    rel_pose = hlp.make_pose_rel(glob.SCENE_OBJECT_INSTANCES[proj_obj.id].pose, new_pose)

    if req.args.update_position:
        ap.position = rel_pose.position

    for ori in ap.orientations:
        if ori.id == req.args.orientation_id:
            ori.orientation = rel_pose.orientation
            break
    else:
        ap.orientations.append(NamedOrientation(req.args.orientation_id, rel_pose.orientation))

    for joint in ap.robot_joints:
        if joint.id == req.args.orientation_id:
            joint.joints = new_joints
            joint.robot_id = req.args.robot.robot_id
            joint.is_valid = True
            break
    else:
        ap.robot_joints.append(ProjectRobotJoints(req.args.orientation_id, req.args.robot.robot_id, new_joints))

    asyncio.ensure_future(notif.notify_project_change_to_others())
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
