#!/usr/bin/env python3
# -*- coding: utf-8 -*-


import asyncio
from typing import Union, List, Dict, Any, Optional, Set
import copy
from contextlib import asynccontextmanager

from arcor2 import object_types_utils as otu, helpers as hlp
from arcor2.data import rpc, events, common, object_type
from arcor2 import aio_persistent_storage as storage
from arcor2.object_types import Generic
from arcor2.services import Service
from arcor2.exceptions import Arcor2Exception
from arcor2.parameter_plugins import PARAM_PLUGINS
from arcor2.parameter_plugins.base import ParameterPluginException
from arcor2.source.logic import program_src, SourceException

from arcor2.server.decorators import scene_needed, project_needed, no_project
from arcor2.server import objects_services_actions as osa, notifications as notif, globals as glob
from arcor2.server.robot import get_end_effector_pose, get_robot_joints
from arcor2.server.project import project_problems, open_project, project_names
from arcor2.server.scene import open_scene, clear_scene


def find_object_action(action: common.Action) -> object_type.ObjectAction:

    assert glob.SCENE

    obj_id, action_type = action.parse_type()
    obj = glob.SCENE.object_or_service(obj_id)

    if obj.type not in glob.ACTIONS:
        raise Arcor2Exception("Unknown object/service type.")

    for act in glob.ACTIONS[obj.type]:
        if act.name == action_type:
            if act.disabled:
                raise Arcor2Exception("Action is disabled.")
            return act
    raise Arcor2Exception("Unknown type of action.")


@asynccontextmanager
async def managed_project(project_id: str, make_copy: bool = False):

    save_back = False

    if glob.PROJECT and glob.PROJECT.id == project_id:
        if make_copy:
            project = copy.deepcopy(glob.PROJECT)
            save_back = True
        else:
            project = glob.PROJECT
    else:
        save_back = True
        project = await storage.get_project(project_id)

    if make_copy:
        project.id = common.uid()

    try:
        yield project
    finally:
        if save_back:
            asyncio.ensure_future(storage.update_project(project))


def unique_name(name: str, existing_names: Set[str]) -> None:

    if not name:
        raise Arcor2Exception("Name has to be set.")

    if name in existing_names:
        raise Arcor2Exception("Name already exists.")


@scene_needed
@project_needed
async def execute_action_cb(req: rpc.project.ExecuteActionRequest) -> \
        Union[rpc.project.ExecuteActionResponse, hlp.RPC_RETURN_TYPES]:

    assert glob.SCENE and glob.PROJECT

    if glob.RUNNING_ACTION:
        return False, f"Action {glob.RUNNING_ACTION} is being executed. Only one action can be executed at a time."

    action = glob.PROJECT.action(req.args.action_id)

    params: Dict[str, Any] = {}

    for param in action.parameters:
        try:
            params[param.id] = PARAM_PLUGINS[param.type].execution_value(glob.TYPE_DEF_DICT, glob.SCENE,
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

    await glob.logger.debug(f"Running action {action.name} ({type(obj)}/{action_name}), params: {params}.")

    # schedule execution and return success
    asyncio.ensure_future(osa.execute_action(getattr(obj, action_name), params))
    return None


async def list_projects_cb(req: rpc.project.ListProjectsRequest) -> \
        Union[rpc.project.ListProjectsResponse, hlp.RPC_RETURN_TYPES]:

    data: List[rpc.project.ListProjectsResponseData] = []

    projects = await storage.get_projects()

    scenes: Dict[str, common.Scene] = {}

    # TODO do this in parallel?
    for project_iddesc in projects.items:

        try:
            project = await storage.get_project(project_iddesc.id)
        except Arcor2Exception as e:
            await glob.logger.warning(f"Ignoring project {project_iddesc.id} due to error: {e}")
            continue

        pd = rpc.project.ListProjectsResponseData(id=project.id, desc=project.desc, name=project.name,
                                                  scene_id=project.scene_id)
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
            pd.problems.append(e.message)

    return rpc.project.ListProjectsResponse(data=data)


@scene_needed
@project_needed
async def add_action_point_joints_cb(req: rpc.project.AddActionPointJointsRequest) -> \
        Union[rpc.project.AddActionPointJointsResponse, hlp.RPC_RETURN_TYPES]:

    assert glob.SCENE and glob.PROJECT

    ap = glob.PROJECT.action_point(req.args.action_point_id)

    unique_name(req.args.name, ap.joints_names())

    new_joints = await get_robot_joints(req.args.robot_id)

    prj = common.ProjectRobotJoints(common.uid(), req.args.name, req.args.robot_id, new_joints, True)
    ap.robot_joints.append(prj)
    glob.PROJECT.update_modified()
    asyncio.ensure_future(notif.broadcast_event(events.JointsChanged(events.EventType.ADD, ap.id, data=prj)))
    return None


@scene_needed
@project_needed
async def update_action_point_joints_cb(req: rpc.project.UpdateActionPointJointsRequest) -> \
        Union[rpc.project.UpdateActionPointJointsResponse, hlp.RPC_RETURN_TYPES]:

    assert glob.SCENE and glob.PROJECT

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
async def remove_action_point_joints_cb(req: rpc.project.RemoveActionPointJointsRequest) -> \
        Union[rpc.project.RemoveActionPointJointsResponse, hlp.RPC_RETURN_TYPES]:
    """
    Removes joints from action point.
    :param req:
    :return:
    """

    assert glob.SCENE and glob.PROJECT

    ap, joints = glob.PROJECT.ap_and_joints(req.args.joints_id)

    for act in glob.PROJECT.actions():
        for param in act.parameters:
            if PARAM_PLUGINS[param.type].uses_robot_joints(glob.PROJECT, act.id, param.id, req.args.joints_id):
                return False, f"Joints used in action {act.name} (parameter {param.id})."

    joints_to_be_removed = ap.joints(req.args.joints_id)
    ap.robot_joints = [joints for joints in ap.robot_joints if joints.id != req.args.joints_id]

    glob.PROJECT.update_modified()
    asyncio.ensure_future(notif.broadcast_event(events.JointsChanged(events.EventType.REMOVE,
                                                                     data=joints_to_be_removed)))
    return None


@scene_needed
@project_needed
async def rename_action_point_cb(req: rpc.project.RenameActionPointRequest) -> \
        Union[rpc.project.RenameActionPointResponse, hlp.RPC_RETURN_TYPES]:

    assert glob.SCENE and glob.PROJECT

    ap = glob.PROJECT.action_point(req.args.action_point_id)

    if req.args.new_name == ap.name:
        return None

    if not hlp.is_valid_identifier(req.args.new_name):
        return False, "Name has to be valid Python identifier."

    unique_name(req.args.new_name, glob.PROJECT.action_points_names)
    ap.name = req.args.new_name

    glob.PROJECT.update_modified()
    asyncio.ensure_future(notif.broadcast_event(events.ActionPointChanged(events.EventType.UPDATE_BASE,
                                                                          data=ap.bare())))
    return None


@scene_needed
@project_needed
async def update_action_point_parent_cb(req: rpc.project.UpdateActionPointParentRequest) -> \
        Union[rpc.project.UpdateActionPointParentResponse, hlp.RPC_RETURN_TYPES]:

    assert glob.SCENE and glob.PROJECT

    ap = glob.PROJECT.action_point(req.args.action_point_id)

    if req.args.new_parent_id == ap.parent:
        return None

    if not ap.parent and req.args.new_parent_id:
        # AP position and all orientations will become relative to the parent
        new_parent = glob.SCENE.object(req.args.new_parent_id)
        ap.position = hlp.make_pose_rel(new_parent.pose, common.Pose(ap.position, common.Orientation())).position
        for ori in ap.orientations:
            ori.orientation = hlp.make_orientation_rel(new_parent.pose.orientation, ori.orientation)

    elif ap.parent and not req.args.new_parent_id:
        # AP position and all orientations will become absolute
        old_parent = glob.SCENE.object(ap.parent)
        ap.position = hlp.make_pose_abs(old_parent.pose, common.Pose(ap.position, common.Orientation())).position
        for ori in ap.orientations:
            ori.orientation = hlp.make_orientation_abs(old_parent.pose.orientation, ori.orientation)
    else:

        assert ap.parent is not None

        # AP position and all orientations will become relative to another parent
        old_parent = glob.SCENE.object(ap.parent)
        new_parent = glob.SCENE.object(req.args.new_parent_id)

        abs_ap_pose = hlp.make_pose_abs(old_parent.pose, common.Pose(ap.position, common.Orientation()))
        ap.position = hlp.make_pose_rel(new_parent.pose, abs_ap_pose).position

        for ori in ap.orientations:
            ori.orientation = hlp.make_orientation_abs(old_parent.pose.orientation, ori.orientation)
            ori.orientation = hlp.make_orientation_rel(new_parent.pose.orientation, ori.orientation)

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
async def update_action_point_position_cb(req: rpc.project.UpdateActionPointPositionRequest) -> \
        Union[rpc.project.UpdateActionPointPositionResponse, hlp.RPC_RETURN_TYPES]:

    assert glob.SCENE and glob.PROJECT

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
async def update_action_point_using_robot_cb(req: rpc.project.UpdateActionPointUsingRobotRequest) -> \
        Union[rpc.project.UpdateActionPointUsingRobotResponse, hlp.RPC_RETURN_TYPES]:

    assert glob.SCENE and glob.PROJECT

    ap = glob.PROJECT.action_point(req.args.action_point_id)
    new_pose = await get_end_effector_pose(req.args.robot.robot_id, req.args.robot.end_effector)

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

    ap = glob.PROJECT.action_point(req.args.action_point_id)

    unique_name(req.args.name, ap.orientation_names())
    orientation = common.NamedOrientation(common.uid(), req.args.name, req.args.orientation)
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

    orientation = glob.PROJECT.orientation(req.args.orientation_id)
    orientation.orientation = req.args.orientation

    glob.PROJECT.update_modified()
    asyncio.ensure_future(notif.broadcast_event(events.OrientationChanged(events.EventType.UPDATE, data=orientation)))
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

    ap = glob.PROJECT.action_point(req.args.action_point_id)
    unique_name(req.args.name, ap.orientation_names())
    new_pose = await get_end_effector_pose(req.args.robot.robot_id, req.args.robot.end_effector)

    if ap.parent:
        obj = glob.SCENE_OBJECT_INSTANCES[ap.parent]
        new_pose = hlp.make_pose_rel(obj.pose, new_pose)

    orientation = common.NamedOrientation(common.uid(), req.args.name, new_pose.orientation)
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

    ap = glob.PROJECT.action_point(req.args.action_point_id)
    new_pose = await get_end_effector_pose(req.args.robot.robot_id, req.args.robot.end_effector)

    if ap.parent:

        obj = glob.SCENE_OBJECT_INSTANCES[ap.parent]
        new_pose = hlp.make_pose_rel(obj.pose, new_pose)

    ori = glob.PROJECT.orientation(req.args.orientation_id)
    ori.orientation = new_pose.orientation

    glob.PROJECT.update_modified()
    asyncio.ensure_future(notif.broadcast_event(events.OrientationChanged(events.EventType.UPDATE, data=ori)))
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

    ap, orientation = glob.PROJECT.ap_and_orientation(req.args.action_point_id)

    for act in glob.PROJECT.actions():
        for param in act.parameters:
            if PARAM_PLUGINS[param.type].uses_orientation(glob.PROJECT, act.id, param.id, req.args.orientation_id):
                return False, f"Orientation used in action {act.name} (parameter {param.id})."

    ap.orientations = [ori for ori in ap.orientations if ori.id != req.args.orientation_id]

    glob.PROJECT.update_modified()
    asyncio.ensure_future(notif.broadcast_event(events.OrientationChanged(events.EventType.REMOVE, data=orientation)))
    return None


async def open_project_cb(req: rpc.project.OpenProjectRequest) -> \
        Union[rpc.project.OpenProjectResponse, hlp.RPC_RETURN_TYPES]:

    # TODO validate using project_problems?
    try:
        await open_project(req.args.id)
    except Arcor2Exception as e:
        await glob.logger.exception(f"Failed to open project {req.args.id}.")
        return False, e.message

    return None


@scene_needed
@project_needed
async def save_project_cb(req: rpc.project.SaveProjectRequest) -> \
        Union[rpc.project.SaveProjectResponse, hlp.RPC_RETURN_TYPES]:

    assert glob.SCENE and glob.PROJECT
    await storage.update_project(glob.PROJECT)
    glob.PROJECT.modified = (await storage.get_project(glob.PROJECT.id)).modified
    asyncio.ensure_future(notif.broadcast_event(events.ProjectSaved()))
    return None


@no_project
async def new_project_cb(req: rpc.project.NewProjectRequest) -> Union[rpc.project.NewProjectResponse,
                                                                      hlp.RPC_RETURN_TYPES]:

    unique_name(req.args.name, (await project_names()))

    if glob.SCENE:
        if glob.SCENE.id != req.args.scene_id:
            return False, "Another scene is opened."

        if glob.SCENE.has_changes():
            await storage.update_scene(glob.SCENE)
            glob.SCENE.modified = (await storage.get_scene(glob.SCENE.id)).modified

    else:

        if req.args.scene_id not in {scene.id for scene in (await storage.get_scenes()).items}:
            return False, "Unknown scene id."

        await open_scene(req.args.scene_id)

    glob.PROJECT = common.Project(common.uid(), req.args.name, req.args.scene_id, desc=req.args.desc,
                                  has_logic=req.args.has_logic)
    asyncio.ensure_future(notif.broadcast_event(events.ProjectChanged(events.EventType.ADD, data=glob.PROJECT)))
    return None


@scene_needed
@project_needed
async def close_project_cb(req: rpc.project.CloseProjectRequest) -> Union[rpc.project.CloseProjectResponse,
                                                                          hlp.RPC_RETURN_TYPES]:
    assert glob.PROJECT

    if not req.args.force and glob.PROJECT.has_changes():
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

    unique_name(req.args.name, glob.PROJECT.action_points_names)

    if not hlp.is_valid_identifier(req.args.name):
        return False, "Name has to be valid Python identifier."

    ap = common.ProjectActionPoint(common.uid(), req.args.name, req.args.position, req.args.parent)
    glob.PROJECT.action_points.append(ap)

    glob.PROJECT.update_modified()
    asyncio.ensure_future(notif.broadcast_event(events.ActionPointChanged(events.EventType.ADD, data=ap)))
    return None


@scene_needed
@project_needed
async def remove_action_point_cb(req: rpc.project.RemoveActionPointRequest) -> \
        Union[rpc.project.RemoveActionPointResponse, hlp.RPC_RETURN_TYPES]:

    assert glob.PROJECT

    ap = glob.PROJECT.action_point(req.args.id)

    for act in glob.PROJECT.actions():
        for param in act.parameters:

            for joints in ap.robot_joints:
                if PARAM_PLUGINS[param.type].uses_robot_joints(glob.PROJECT, act.id, param.id, joints.id):
                    return False, f"Joints {joints.name} used in action {act.name} (parameter {param.id})."

            for ori in ap.orientations:
                if PARAM_PLUGINS[param.type].uses_orientation(glob.PROJECT, act.id, param.id, ori.id):
                    return False, f"Orientation {ori.name} used in action {act.name} (parameter {param.id})."

            # TODO some hypothetical parameter type could use just bare ActionPoint (its position)

    glob.PROJECT.action_points = [acp for acp in glob.PROJECT.action_points if acp.id != req.args.id]
    glob.PROJECT.update_modified()
    asyncio.ensure_future(notif.broadcast_event(events.ActionPointChanged(events.EventType.REMOVE, data=ap.bare())))
    return None


def check_action_params(project: common.Project, action: common.Action, object_action: object_type.ObjectAction) \
        -> None:

    assert glob.SCENE

    _, action_type = action.parse_type()

    assert action_type == object_action.name

    if len(object_action.parameters) != len(action.parameters):
        raise Arcor2Exception("Unexpected number of parameters.")

    for req_param in object_action.parameters:
        for given_param in action.parameters:
            if req_param.name == given_param.id and req_param.type == given_param.type:
                break
        else:
            raise Arcor2Exception(f"Action parameter {req_param.name}/{req_param.type} is not set or has invalid type.")

    # check values of parameters
    for param in action.parameters:

        if param.type not in PARAM_PLUGINS:
            raise Arcor2Exception(f"Parameter {param.id} of action {action.name} has unknown type: {param.type}.")

        try:
            PARAM_PLUGINS[param.type].value(glob.TYPE_DEF_DICT, glob.SCENE, project, action.id, param.id)
        except ParameterPluginException as e:
            raise Arcor2Exception(f"Parameter {param.id} of action {action.name} has invalid value. {str(e)}")


@scene_needed
@project_needed
async def add_action_cb(req: rpc.project.AddActionRequest) -> \
        Union[rpc.project.AddActionResponse, hlp.RPC_RETURN_TYPES]:

    assert glob.PROJECT
    assert glob.SCENE

    ap = glob.PROJECT.action_point(req.args.action_point_id)

    unique_name(req.args.name, glob.PROJECT.action_user_names())

    if not hlp.is_valid_identifier(req.args.name):
        return False, "Action name has to be valid Python identifier."

    new_action = common.Action(common.uid(), req.args.name, req.args.type, req.args.parameters)

    updated_project = copy.deepcopy(glob.PROJECT)
    updated_ap = updated_project.action_point(req.args.action_point_id)
    updated_ap.actions.append(new_action)

    check_action_params(updated_project, new_action, find_object_action(new_action))

    ap.actions.append(new_action)

    glob.PROJECT.update_modified()
    asyncio.ensure_future(notif.broadcast_event(events.ActionChanged(events.EventType.ADD, ap.id, data=new_action)))
    return None


@scene_needed
@project_needed
async def update_action_cb(req: rpc.project.UpdateActionRequest) -> Union[rpc.project.UpdateActionResponse,
                                                                          hlp.RPC_RETURN_TYPES]:

    assert glob.PROJECT
    assert glob.SCENE

    updated_project = copy.deepcopy(glob.PROJECT)

    updated_action = updated_project.action(req.args.action_id)
    updated_action.parameters = req.args.parameters

    check_action_params(updated_project, updated_action, find_object_action(updated_action))

    orig_action = glob.PROJECT.action(req.args.action_id)
    orig_action.parameters = updated_action.parameters

    glob.PROJECT.update_modified()
    asyncio.ensure_future(notif.broadcast_event(events.ActionChanged(events.EventType.UPDATE,
                                                                     data=updated_action)))
    return None


def check_action_usage(action: common.Action) -> None:

    assert glob.PROJECT

    for ap in glob.PROJECT.action_points:
        for act in ap.actions:
            for inp in act.inputs:
                if inp.default == action.id:
                    raise Arcor2Exception(f"Action used as an input for another action ({act.name}).")
            for out in act.outputs:
                if out.default == action.id:
                    raise Arcor2Exception(f"Action used as an output for another action ({act.name}).")


@scene_needed
@project_needed
async def remove_action_cb(req: rpc.project.RemoveActionRequest) -> Union[rpc.project.RemoveActionResponse,
                                                                          hlp.RPC_RETURN_TYPES]:

    assert glob.PROJECT
    assert glob.SCENE

    ap, action = glob.PROJECT.action_point_and_action(req.args.id)
    check_action_usage(action)
    ap.actions = [act for act in ap.actions if act.id != req.args.id]

    glob.PROJECT.update_modified()
    asyncio.ensure_future(notif.broadcast_event(events.ActionChanged(events.EventType.REMOVE, data=action.bare())))
    return None


@scene_needed
@project_needed
async def update_action_logic_cb(req: rpc.project.UpdateActionLogicRequest) -> \
        Union[rpc.project.UpdateActionLogicResponse, hlp.RPC_RETURN_TYPES]:

    assert glob.PROJECT
    assert glob.SCENE

    action = glob.PROJECT.action(req.args.action_id)

    allowed_values = glob.PROJECT.action_ids() | common.ActionIOEnum.set() | {""}

    for inp in req.args.inputs:
        if inp.default not in allowed_values:
            return False, "Unknown input value."

    for out in req.args.outputs:
        if out.default not in allowed_values:
            return False, "Unknown output value."

    action.inputs = req.args.inputs
    action.outputs = req.args.outputs

    glob.PROJECT.update_modified()
    asyncio.ensure_future(notif.broadcast_event(events.ActionChanged(events.EventType.UPDATE, data=action)))
    return None


@no_project
async def delete_project_cb(req: rpc.project.DeleteProjectRequest) -> \
        Union[rpc.project.DeleteProjectResponse, hlp.RPC_RETURN_TYPES]:

    project = await storage.get_project(req.args.id)
    await storage.delete_project(req.args.id)
    asyncio.ensure_future(notif.broadcast_event(events.ProjectChanged(events.EventType.REMOVE,
                                                                      data=project.bare())))
    return None


async def rename_project_cb(req: rpc.project.RenameProjectRequest) -> \
        Union[rpc.project.RenameProjectResponse, hlp.RPC_RETURN_TYPES]:

    unique_name(req.args.new_name, (await project_names()))

    async with managed_project(req.args.project_id) as project:

        project.name = req.args.new_name
        project.update_modified()

        asyncio.ensure_future(notif.broadcast_event(events.ProjectChanged(events.EventType.UPDATE_BASE,
                                                                          data=project.bare())))
    return None


async def copy_project_cb(req: rpc.project.CopyProjectRequest) -> \
        Union[rpc.project.CopyProjectResponse, hlp.RPC_RETURN_TYPES]:

    unique_name(req.args.target_name, (await project_names()))

    async with managed_project(req.args.source_id, make_copy=True) as project:

        project.name = req.args.target_name
        asyncio.ensure_future(notif.broadcast_event(events.ProjectChanged(events.EventType.UPDATE_BASE,
                                                                          data=project.bare())))

    return None


async def update_project_description_cb(req: rpc.project.UpdateProjectDescriptionRequest) -> \
        Union[rpc.project.UpdateProjectDescriptionResponse, hlp.RPC_RETURN_TYPES]:

    async with managed_project(req.args.project_id) as project:

        project.desc = req.args.new_description
        project.update_modified()

        asyncio.ensure_future(notif.broadcast_event(events.ProjectChanged(events.EventType.UPDATE_BASE,
                                                                          data=project.bare())))
    return None


async def update_project_has_logic_cb(req: rpc.project.UpdateProjectHasLogicRequest) -> \
        Union[rpc.project.UpdateProjectHasLogicResponse, hlp.RPC_RETURN_TYPES]:

    async with managed_project(req.args.project_id) as project:

        if project.has_logic and not req.args.new_has_logic:

            for act in project.actions():
                act.inputs.clear()
                act.outputs.clear()

                if glob.PROJECT and glob.PROJECT.id == req.args.project_id:
                    asyncio.ensure_future(notif.broadcast_event(events.ActionChanged(events.EventType.UPDATE,
                                                                                     data=act)))

        project.has_logic = req.args.new_has_logic
        project.update_modified()
        asyncio.ensure_future(notif.broadcast_event(events.ProjectChanged(events.EventType.UPDATE_BASE,
                                                                          data=project.bare())))
    return None


@project_needed
async def rename_action_point_joints_cb(req: rpc.project.RenameActionPointJointsRequest) -> \
        Union[rpc.project.RenameActionPointJointsResponse, hlp.RPC_RETURN_TYPES]:

    assert glob.PROJECT

    ap, joints = glob.PROJECT.ap_and_joints(req.args.joints_id)
    unique_name(req.args.new_name, ap.joints_names())
    joints.name = req.args.new_name
    glob.PROJECT.update_modified()
    asyncio.ensure_future(notif.broadcast_event(events.JointsChanged(events.EventType.UPDATE_BASE, data=joints)))

    return None


@project_needed
async def rename_action_point_orientation_cb(req: rpc.project.RenameActionPointOrientationRequest) -> \
        Union[rpc.project.RenameActionPointOrientationResponse, hlp.RPC_RETURN_TYPES]:

    assert glob.PROJECT

    ap, ori = glob.PROJECT.ap_and_orientation(req.args.orientation_id)
    unique_name(req.args.new_name, ap.orientation_names())
    ori.name = req.args.new_name
    glob.PROJECT.update_modified()
    asyncio.ensure_future(notif.broadcast_event(events.OrientationChanged(events.EventType.UPDATE_BASE, data=ori)))

    return None


@project_needed
async def rename_action_cb(req: rpc.project.RenameActionRequest) -> \
        Union[rpc.project.RenameActionResponse, hlp.RPC_RETURN_TYPES]:

    assert glob.PROJECT

    unique_name(req.args.new_name, glob.PROJECT.action_user_names())
    act = glob.PROJECT.action(req.args.action_id)
    act.name = req.args.new_name

    glob.PROJECT.update_modified()
    asyncio.ensure_future(notif.broadcast_event(events.ActionChanged(events.EventType.UPDATE_BASE, data=act)))

    return None
