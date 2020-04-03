#!/usr/bin/env python3
# -*- coding: utf-8 -*-


import asyncio
from typing import Union, List, Dict, Any, Optional
import uuid
import copy

from arcor2 import object_types_utils as otu, helpers as hlp
from arcor2.data.common import Scene, ProjectRobotJoints, NamedOrientation, Project, ProjectActionPoint, Action,\
    ActionIOEnum
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
from arcor2.server.scene import open_scene, clear_scene


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

    # TODO do this in parallel?
    for project_iddesc in projects.items:

        try:
            project = await storage.get_project(project_iddesc.id)
        except Arcor2Exception as e:
            await glob.logger.warning(f"Ignoring project {project_iddesc.id} due to error: {e}")
            continue

        pd = rpc.project.ListProjectsResponseData(project.id, project.desc, project.scene_id)
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
async def add_action_point_joints_cb(req: rpc.project.AddActionPointJointsRequest) -> \
        Union[rpc.project.AddActionPointJointsResponse, hlp.RPC_RETURN_TYPES]:

    assert glob.SCENE and glob.PROJECT

    try:
        ap = glob.PROJECT.action_point(req.args.action_point_id)
    except Arcor2Exception:
        return False, "Invalid action point."

    for joints in ap.robot_joints:
        if req.args.name == joints.name:
            return False, "Name already exists."

    try:
        new_joints = await get_robot_joints(req.args.robot_id)
    except Arcor2Exception as e:
        return False, str(e)

    prj = ProjectRobotJoints(uuid.uuid4().hex, req.args.name, req.args.robot_id, new_joints, True)
    ap.robot_joints.append(prj)
    glob.PROJECT.update_modified()
    asyncio.ensure_future(notif.broadcast_event(events.JointsChanged(events.EventType.ADD, ap.id, data=prj)))
    return None


@scene_needed
@project_needed
async def update_action_point_joints_cb(req: rpc.project.UpdateActionPointJointsRequest) -> \
        Union[rpc.project.UpdateActionPointJointsResponse, hlp.RPC_RETURN_TYPES]:

    assert glob.SCENE and glob.PROJECT

    try:
        ap = glob.PROJECT.action_point(req.args.id)
    except Arcor2Exception:
        return False, "Invalid action point."

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

    glob.PROJECT.update_modified()
    asyncio.ensure_future(notif.broadcast_event(events.JointsChanged(events.EventType.UPDATE, ap.id,
                                                                     data=robot_joints)))
    return None


@scene_needed
@project_needed
async def remove_action_point_joints_cb(req: rpc.project.RemoveActionPointJointsRequest) -> \
        Union[rpc.project.RemoveActionPointJointsResponse, hlp.RPC_RETURN_TYPES]:
    """
    Removes joints from action point.
    :param req:
    :return:
    """

    assert glob.SCENE and glob.PROJECT

    # TODO candidate for decorator?
    try:
        ap = glob.PROJECT.action_point(req.args.action_point_id)
    except Arcor2Exception:
        return False, "Invalid action point."

    for joints in ap.robot_joints:
        if joints.id == req.args.joints_id:
            break
    else:
        return False, "Unknown joints."

    for act in glob.PROJECT.actions():
        for param in act.parameters:
            if PARAM_PLUGINS[param.type].uses_robot_joints(glob.PROJECT, act.id, param.id, req.args.joints_id):
                return False, f"Joints used in action {act.name} (parameter {param.id})."

    joints_to_be_removed = ap.joints(req.args.joints_id)
    ap.robot_joints = [joints for joints in ap.robot_joints if joints.id != req.args.joints_id]

    glob.PROJECT.update_modified()
    asyncio.ensure_future(notif.broadcast_event(events.JointsChanged(events.EventType.REMOVE, ap.id,
                                                                     data=joints_to_be_removed)))
    return None


@scene_needed
@project_needed
async def update_action_point_cb(req: rpc.project.UpdateActionPointRequest) -> \
        Union[rpc.project.UpdateActionPointResponse, hlp.RPC_RETURN_TYPES]:

    assert glob.SCENE and glob.PROJECT

    ap = glob.PROJECT.action_point(req.args.action_point_id)

    change = False

    if req.args.new_name is not None:

        if not hlp.is_valid_identifier(req.args.new_name):
            return False, "Name has to be valid Python identifier."

        if req.args.new_name in glob.PROJECT.action_points_names:
            return False, "Name is not unique."

        ap.name = req.args.new_name
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
        for joints in ap.robot_joints:
            asyncio.ensure_future(
                notif.broadcast_event(events.JointsChanged(events.EventType.UPDATE, ap.id, data=joints)))
        change = True

    if not change:
        return False, "No change requested."

    glob.PROJECT.update_modified()
    asyncio.ensure_future(notif.broadcast_event(events.ActionPointChanged(events.EventType.UPDATE_BASE,
                                                                          data=ap.bare())))
    return None


@scene_needed
@project_needed
async def update_action_point_using_robot_cb(req: rpc.project.UpdateActionPointUsingRobotRequest) -> \
        Union[rpc.project.UpdateActionPointUsingRobotResponse, hlp.RPC_RETURN_TYPES]:

    assert glob.SCENE and glob.PROJECT

    try:
        ap = glob.PROJECT.action_point(req.args.action_point_id)
    except Arcor2Exception:
        return False, "Invalid action point."

    try:
        new_pose = await get_end_effector_pose(req.args.robot.robot_id, req.args.robot.end_effector)
    except RobotPoseException as e:
        return False, str(e)

    if ap.parent:

        obj = glob.SCENE_OBJECT_INSTANCES[ap.parent]
        new_pose = hlp.make_pose_rel(obj.pose, new_pose)

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
async def add_action_point_orientation_cb(req: rpc.project.AddActionPointOrientationRequest) -> \
        Union[rpc.project.AddActionPointOrientationResponse, hlp.RPC_RETURN_TYPES]:
    """
    Adds orientation and joints to the action point.
    :param req:
    :return:
    """

    assert glob.SCENE and glob.PROJECT

    try:
        ap = glob.PROJECT.action_point(req.args.action_point_id)
    except Arcor2Exception:
        return False, "Invalid action point."

    for ori in ap.orientations:
        if ori.name == req.args.name:
            return False, "Orientation with desired name already exists."

    orientation = NamedOrientation(uuid.uuid4().hex, req.args.name, req.args.orientation)
    ap.orientations.append(orientation)

    glob.PROJECT.update_modified()
    asyncio.ensure_future(notif.broadcast_event(events.OrientationChanged(events.EventType.ADD, ap.id,
                                                                          data=orientation)))
    return None


@scene_needed
@project_needed
async def update_action_point_orientation_cb(req: rpc.project.UpdateActionPointOrientationRequest) -> \
        Union[rpc.project.UpdateActionPointOrientationUsingRobotResponse, hlp.RPC_RETURN_TYPES]:
    """
    Updates orientation of the action point.
    :param req:
    :return:
    """

    assert glob.SCENE and glob.PROJECT

    ap = glob.PROJECT.action_point(req.args.action_point_id)
    orientation = ap.orientation(req.args.orientation_id)
    orientation.orientation = req.args.orientation

    glob.PROJECT.update_modified()
    asyncio.ensure_future(notif.broadcast_event(events.OrientationChanged(events.EventType.UPDATE, ap.id,
                                                                          data=orientation)))
    return None


@scene_needed
@project_needed
async def add_action_point_orientation_using_robot_cb(req: rpc.project.AddActionPointOrientationUsingRobotRequest) -> \
        Union[rpc.project.AddActionPointOrientationUsingRobotResponse, hlp.RPC_RETURN_TYPES]:
    """
    Adds orientation and joints to the action point.
    :param req:
    :return:
    """

    assert glob.SCENE and glob.PROJECT

    try:
        ap = glob.PROJECT.action_point(req.args.action_point_id)
    except Arcor2Exception:
        return False, "Invalid action point."

    for ori in ap.orientations:
        if ori.name == req.args.name:
            return False, "Orientation with desired name already exists."

    try:
        new_pose = await get_end_effector_pose(req.args.robot.robot_id, req.args.robot.end_effector)
    except RobotPoseException as e:
        return False, str(e)

    if ap.parent:
        obj = glob.SCENE_OBJECT_INSTANCES[ap.parent]
        new_pose = hlp.make_pose_rel(obj.pose, new_pose)

    orientation = NamedOrientation(uuid.uuid4().hex, req.args.name, new_pose.orientation)
    ap.orientations.append(orientation)

    glob.PROJECT.update_modified()
    asyncio.ensure_future(notif.broadcast_event(events.OrientationChanged(events.EventType.ADD, ap.id,
                                                                          data=orientation)))
    return None


@scene_needed
@project_needed
async def update_action_point_orientation_using_robot_cb(
        req: rpc.project.UpdateActionPointOrientationUsingRobotRequest) -> \
        Union[rpc.project.UpdateActionPointOrientationUsingRobotResponse, hlp.RPC_RETURN_TYPES]:
    """
    Updates orientation and joint of the action point.
    :param req:
    :return:
    """

    assert glob.SCENE and glob.PROJECT

    try:
        ap = glob.PROJECT.action_point(req.args.action_point_id)
    except Arcor2Exception:
        return False, "Invalid action point."

    try:
        new_pose = await get_end_effector_pose(req.args.robot.robot_id, req.args.robot.end_effector)
    except RobotPoseException as e:
        return False, str(e)

    if ap.parent:

        obj = glob.SCENE_OBJECT_INSTANCES[ap.parent]
        new_pose = hlp.make_pose_rel(obj.pose, new_pose)

    for ori in ap.orientations:
        if ori.id == req.args.orientation_id:
            ori.orientation = new_pose.orientation
            orientation = ori
            break
    else:
        return False, "Unknown orientation."

    glob.PROJECT.update_modified()
    asyncio.ensure_future(notif.broadcast_event(events.OrientationChanged(events.EventType.UPDATE, ap.id,
                                                                          data=orientation)))
    return None


@scene_needed
@project_needed
async def remove_action_point_orientation_cb(req: rpc.project.RemoveActionPointOrientationRequest) -> \
        Union[rpc.project.RemoveActionPointOrientationResponse, hlp.RPC_RETURN_TYPES]:
    """
    Removes orientation.
    :param req:
    :return:
    """

    assert glob.SCENE and glob.PROJECT

    try:
        ap = glob.PROJECT.action_point(req.args.action_point_id)
    except Arcor2Exception:
        return False, "Invalid action point."

    for ori in ap.orientations:
        if ori.id == req.args.orientation_id:
            orientation = ori
            break
    else:
        return False, "Unknown orientation."

    for act in glob.PROJECT.actions():
        for param in act.parameters:
            if PARAM_PLUGINS[param.type].uses_orientation(glob.PROJECT, act.id, param.id, req.args.orientation_id):
                return False, f"Orientation used in action {act.name} (parameter {param.id})."

    ap.orientations = [ori for ori in ap.orientations if ori.id != req.args.orientation_id]

    glob.PROJECT.update_modified()
    asyncio.ensure_future(notif.broadcast_event(events.OrientationChanged(events.EventType.REMOVE, ap.id,
                                                                          data=orientation)))
    return None


async def open_project_cb(req: rpc.project.OpenProjectRequest) -> \
        Union[rpc.project.OpenProjectResponse, hlp.RPC_RETURN_TYPES]:

    # TODO validate using project_problems?
    try:
        await open_project(req.args.id)
    except Arcor2Exception as e:
        await glob.logger.exception(f"Failed to open project {req.args.id}.")
        return False, str(e)

    return None


@scene_needed
@project_needed
async def save_project_cb(req: rpc.project.SaveProjectRequest) -> \
        Union[rpc.project.SaveProjectResponse, hlp.RPC_RETURN_TYPES]:

    assert glob.SCENE and glob.PROJECT
    await storage.update_project(glob.PROJECT)
    # TODO get generated 'modified' from storage and update ours?
    asyncio.ensure_future(notif.broadcast_event(events.ProjectSaved()))
    return None


@no_project
async def new_project_cb(req: rpc.project.NewProjectRequest) -> Union[rpc.project.NewProjectResponse,
                                                                      hlp.RPC_RETURN_TYPES]:

    for project_id in (await storage.get_projects()).items:
        project = await storage.get_project(project_id.id)
        if req.args.name == project.name:
            return False, "Name already used."

    if glob.SCENE:
        if glob.SCENE.id != req.args.scene_id:
            return False, "Another scene is opened."

        # TODO save scene if not saved?

    else:

        if req.args.scene_id not in {scene.id for scene in (await storage.get_scenes()).items}:
            return False, "Unknown scene id."

        await open_scene(req.args.scene_id)

    glob.PROJECT = Project(uuid.uuid4().hex, req.args.name, req.args.scene_id, desc=req.args.desc,
                           has_logic=req.args.has_logic)
    asyncio.ensure_future(notif.broadcast_event(events.ProjectChanged(events.EventType.ADD, data=glob.PROJECT)))
    return None


@scene_needed
@project_needed
async def close_project_cb(req: rpc.project.CloseProjectRequest) -> Union[rpc.project.CloseProjectResponse,
                                                                          hlp.RPC_RETURN_TYPES]:
    assert glob.PROJECT

    if not req.args.force:

        saved_project = await storage.get_project(glob.PROJECT.id)

        if saved_project.modified and glob.PROJECT.modified and \
                saved_project.modified < glob.PROJECT.modified:
            return False, "Project has unsaved changes."

    glob.PROJECT = None
    asyncio.ensure_future(notif.broadcast_event(events.ProjectChanged(events.EventType.UPDATE)))

    await clear_scene()
    asyncio.ensure_future(notif.broadcast_event(events.SceneChanged(events.EventType.UPDATE)))

    return None


@scene_needed
@project_needed
async def add_action_point_cb(req: rpc.project.AddActionPointRequest) -> \
        Union[rpc.project.AddActionPointResponse, hlp.RPC_RETURN_TYPES]:

    assert glob.PROJECT

    if req.args.name in glob.PROJECT.action_points_names:
        return False, "Action point name is already used."

    ap = ProjectActionPoint(uuid.uuid4().hex, req.args.name, req.args.position)
    glob.PROJECT.action_points.append(ap)

    glob.PROJECT.update_modified()
    asyncio.ensure_future(notif.broadcast_event(events.ActionPointChanged(events.EventType.ADD, data=ap)))
    return None


def check_action_params(action: Action) -> None:

    assert glob.SCENE
    assert glob.PROJECT

    # TODO check if all required parameters are set

    for param in action.parameters:

        if param.type not in PARAM_PLUGINS:
            raise Arcor2Exception(f"Parameter {param.id} of action {action.name} has unknown type: {param.type}.")

        try:
            PARAM_PLUGINS[param.type].value(glob.TYPE_DEF_DICT, glob.SCENE, glob.PROJECT, action.id, param.id)
        except ParameterPluginException as e:
            raise Arcor2Exception(f"Parameter {param.id} of action {action.name} has invalid value. {str(e)}")


@scene_needed
@project_needed
async def add_action_cb(req: rpc.project.AddActionRequest) -> \
        Union[rpc.project.AddActionResponse, hlp.RPC_RETURN_TYPES]:

    assert glob.PROJECT
    assert glob.SCENE

    try:
        ap = glob.PROJECT.action_point(req.args.action_point_id)
    except Arcor2Exception as e:
        return False, str(e)

    if req.args.name in glob.PROJECT.action_user_names():
        return False, "Action name already exists."

    if not hlp.is_valid_identifier(req.args.name):
        return False, "Action name has to be valid Python identifier."

    action = Action(uuid.uuid4().hex, req.args.name, req.args.type, req.args.parameters)

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

    try:
        check_action_params(action)
    except Arcor2Exception as e:
        return False, str(e)

    ap.actions.append(action)

    glob.PROJECT.update_modified()
    asyncio.ensure_future(notif.broadcast_event(events.ActionChanged(events.EventType.ADD, ap.id, data=action)))
    return None


@scene_needed
@project_needed
async def update_action_cb(req: rpc.project.UpdateActionRequest) -> Union[rpc.project.UpdateActionResponse,
                                                                          hlp.RPC_RETURN_TYPES]:

    assert glob.PROJECT
    assert glob.SCENE

    try:
        ap, action = glob.PROJECT.action_point_and_action(req.args.action_id)
    except Arcor2Exception as e:
        return False, str(e)

    updated_action = copy.deepcopy(action)
    updated_action.parameters = req.args.parameters

    try:
        check_action_params(updated_action)
    except Arcor2Exception as e:
        return False, str(e)

    action.parameters = req.args.parameters

    glob.PROJECT.update_modified()
    asyncio.ensure_future(notif.broadcast_event(events.ActionChanged(events.EventType.UPDATE, ap.id,
                                                                     data=updated_action)))
    return None


@scene_needed
@project_needed
async def remove_action_cb(req: rpc.project.RemoveActionRequest) -> Union[rpc.project.RemoveActionResponse,
                                                                          hlp.RPC_RETURN_TYPES]:

    assert glob.PROJECT
    assert glob.SCENE

    try:
        ap, action = glob.PROJECT.action_point_and_action(req.args.id)
    except Arcor2Exception as e:
        return False, str(e)

    for ap in glob.PROJECT.action_points:
        for act in ap.actions:
            for inp in act.inputs:
                if inp.default == action.id:
                    return False, f"Action used as an input for another action ({act.name})."

    ap.actions = [act for act in ap.actions if act.id != req.args.id]

    glob.PROJECT.update_modified()
    asyncio.ensure_future(notif.broadcast_event(events.ActionChanged(events.EventType.REMOVE, ap.id, data=action)))
    return None


@scene_needed
@project_needed
async def update_action_logic_cb(req: rpc.project.UpdateActionLogicRequest) -> \
        Union[rpc.project.UpdateActionLogicResponse, hlp.RPC_RETURN_TYPES]:

    assert glob.PROJECT
    assert glob.SCENE

    try:
        ap, action = glob.PROJECT.action_point_and_action(req.args.action_id)
    except Arcor2Exception as e:
        return False, str(e)

    allowed_values = glob.PROJECT.action_ids() | ActionIOEnum.set() | {""}

    for inp in req.args.inputs:
        if inp.default not in allowed_values:
            return False, "Unknown input value."

    for out in req.args.outputs:
        if out.default not in allowed_values:
            return False, "Unknown output value."

    action.inputs = req.args.inputs
    action.outputs = req.args.outputs

    glob.PROJECT.update_modified()
    asyncio.ensure_future(notif.broadcast_event(events.ActionChanged(events.EventType.UPDATE, ap.id, data=action)))
    return None
