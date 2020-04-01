#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from typing import Union
import asyncio
import functools
import uuid
from datetime import datetime

from arcor2.exceptions import Arcor2Exception
from arcor2 import aio_persistent_storage as storage, helpers as hlp
from arcor2.data import rpc, events
from arcor2.data import common
from arcor2.object_types import Generic
from arcor2.services import Service

from arcor2.server.robot import get_end_effector_pose, RobotPoseException
from arcor2.server.decorators import scene_needed, no_project, no_scene
from arcor2.server import globals as glob, notifications as notif
from arcor2.server.robot import collision
from arcor2.server.scene import add_object_to_scene, auto_add_object_to_scene, open_scene, add_service_to_scene, clear_scene
from arcor2.server.project import scene_object_pose_updated, remove_object_references_from_projects, projects_using_object, projects


@no_scene
async def new_scene_cb(req: rpc.scene.NewSceneRequest) -> Union[rpc.scene.NewSceneResponse,
                                                                          hlp.RPC_RETURN_TYPES]:
    """
    Creates and opens a new scene on the server. Fails if any scene is open or if scene id/user_id already exists.
    :param req:
    :return:
    """

    assert glob.SCENE is None

    glob.SCENE = common.Scene(uuid.uuid4().hex, req.args.user_id, desc=req.args.desc)
    asyncio.ensure_future(notif.broadcast_event(events.SceneChanged(events.EventType.ADD, data=glob.SCENE)))
    return None


@scene_needed
@no_project
async def close_scene_cb(req: rpc.scene.CloseSceneRequest) -> Union[rpc.scene.CloseSceneResponse,
                                                                          hlp.RPC_RETURN_TYPES]:
    """
    Closes scene on the server.
    :param req:
    :return:
    """

    assert glob.SCENE

    if req.args.force:
        glob.SCENE = None
    else:

        try:
            saved_scene = await storage.get_scene(glob.SCENE.id)

            if saved_scene and saved_scene.last_modified and glob.SCENE.last_modified and \
                    saved_scene.last_modified < glob.SCENE.last_modified:
                return False, "Scene has unsaved changes."

        except storage.PersistentStorageException:
            pass

    await clear_scene()
    asyncio.ensure_future(notif.broadcast_event(events.SceneChanged(events.EventType.UPDATE)))
    return None


@scene_needed
@no_project
async def save_scene_cb(req: rpc.scene.SaveSceneRequest) -> Union[rpc.scene.SaveSceneResponse,
                                                                          hlp.RPC_RETURN_TYPES]:

    assert glob.SCENE

    try:
        stored_scene = await storage.get_scene(glob.SCENE.id)
    except storage.PersistentStorageException:
        # new scene, no need for further checks
        await storage.update_scene(glob.SCENE)
        asyncio.ensure_future(notif.broadcast_event(events.SceneSaved()))
        return None

    # let's check if something important has changed
    for old_obj in stored_scene.objects:
        for new_obj in glob.SCENE.objects:
            if old_obj.id != new_obj.id:
                continue

            if old_obj.pose != new_obj.pose:
                asyncio.ensure_future(scene_object_pose_updated(glob.SCENE.id, new_obj.id))

    await storage.update_scene(glob.SCENE)
    asyncio.ensure_future(notif.broadcast_event(events.SceneSaved()))
    return None


@no_project
async def open_scene_cb(req: rpc.scene.OpenSceneRequest) -> Union[rpc.scene.OpenSceneResponse,
                                                                  hlp.RPC_RETURN_TYPES]:

    try:
        await open_scene(req.args.id)
    except Arcor2Exception as e:
        await glob.logger.exception(f"Failed to open scene {req.args.id}.")
        return False, str(e)
    return None


async def list_scenes_cb(req: rpc.scene.ListScenesRequest) -> \
        Union[rpc.scene.ListScenesResponse, hlp.RPC_RETURN_TYPES]:

    scenes = await storage.get_scenes()
    return rpc.scene.ListScenesResponse(data=scenes.items)


@scene_needed
@no_project
async def add_object_to_scene_cb(req: rpc.scene.AddObjectToSceneRequest) -> \
        Union[rpc.scene.AddObjectToSceneResponse, hlp.RPC_RETURN_TYPES]:

    assert glob.SCENE

    obj = common.SceneObject(uuid.uuid4().hex, req.args.user_id, req.args.type,
                                                            req.args.pose)

    res, msg = await add_object_to_scene(obj)

    if not res:
        return res, msg

    glob.SCENE.last_modified = datetime.now()
    asyncio.ensure_future(notif.broadcast_event(events.SceneObjectChanged(events.EventType.ADD, data=obj)))
    return None


@scene_needed
@no_project
async def auto_add_object_to_scene_cb(req: rpc.scene.AutoAddObjectToSceneRequest) -> \
        Union[rpc.scene.AutoAddObjectToSceneResponse, hlp.RPC_RETURN_TYPES]:
    assert glob.SCENE

    obj = req.args
    res, msg = await auto_add_object_to_scene(obj.type)

    if not res:
        return res, msg

    glob.SCENE.last_modified = datetime.now()
    return None


@scene_needed
@no_project
async def add_service_to_scene_cb(req: rpc.scene.AddServiceToSceneRequest) ->\
        Union[rpc.scene.AddServiceToSceneResponse, hlp.RPC_RETURN_TYPES]:

    assert glob.SCENE

    srv = req.args
    res, msg = await add_service_to_scene(srv)

    if not res:
        return res, msg

    glob.SCENE.services.append(srv)
    glob.SCENE.last_modified = datetime.now()
    asyncio.ensure_future(notif.broadcast_event(events.SceneServiceChanged(events.EventType.ADD, data=srv)))
    return None


@scene_needed
async def scene_object_usage_request_cb(req: rpc.scene.SceneObjectUsageRequest) -> \
        Union[rpc.scene.SceneObjectUsageResponse, hlp.RPC_RETURN_TYPES]:
    """
    Works for both services and objects.
    :param req:
    :return:
    """

    assert glob.SCENE

    if not (any(obj.id == req.args.id for obj in glob.SCENE.objects) or
            any(srv.type == req.args.id for srv in glob.SCENE.services)):
        return False, "Unknown ID."

    resp = rpc.scene.SceneObjectUsageResponse()

    async for project in projects_using_object(glob.SCENE.id, req.args.id):
        resp.data.add(project.id)

    return resp


@scene_needed
async def action_param_values_cb(req: rpc.objects.ActionParamValuesRequest) -> \
        Union[rpc.objects.ActionParamValuesResponse, hlp.RPC_RETURN_TYPES]:

    inst: Union[None, Service, Generic] = None

    # TODO method to get object/service based on ID
    if req.args.id in glob.SCENE_OBJECT_INSTANCES:
        inst = glob.SCENE_OBJECT_INSTANCES[req.args.id]
    elif req.args.id in glob.SERVICES_INSTANCES:
        inst = glob.SERVICES_INSTANCES[req.args.id]
    else:
        return False, "Unknown ID."

    parent_params = {}

    for pp in req.args.parent_params:
        parent_params[pp.id] = pp.value

    try:
        method_name, required_parent_params = inst.DYNAMIC_PARAMS[req.args.param_id]
    except KeyError:
        return False, "Unknown parameter or values not constrained."

    if parent_params.keys() != required_parent_params:
        return False, "Not all required parent params were given."

    # TODO validate method parameters vs parent_params (check types)?

    resp = rpc.objects.ActionParamValuesResponse()

    try:
        method = getattr(inst, method_name)
    except AttributeError:
        await glob.logger.error(f"Unable to get values for parameter {req.args.param_id}, "
                           f"object/service {inst.id} has no method named {method_name}.")
        return False, "System error."

    # TODO update hlp.run_in_executor to support kwargs
    resp.data = await asyncio.get_event_loop().run_in_executor(None, functools.partial(method, **parent_params))
    return resp


@scene_needed
@no_project
async def remove_from_scene_cb(req: rpc.scene.RemoveFromSceneRequest) -> \
        Union[rpc.scene.RemoveFromSceneResponse, hlp.RPC_RETURN_TYPES]:

    assert glob.SCENE

    if req.args.id in glob.SCENE_OBJECT_INSTANCES:

        obj = glob.SCENE.object(req.args.id)
        glob.SCENE.objects = [obj for obj in glob.SCENE.objects if obj.id != req.args.id]
        obj_inst = glob.SCENE_OBJECT_INSTANCES[req.args.id]
        await collision(obj_inst, remove=True)
        del glob.SCENE_OBJECT_INSTANCES[req.args.id]
        asyncio.ensure_future(notif.broadcast_event(events.SceneObjectChanged(events.EventType.REMOVE, data=obj)))

    elif req.args.id in glob.SERVICES_INSTANCES:

        # first check if some object is not using it
        for obj in glob.SCENE.objects:
            if req.args.id in glob.OBJECT_TYPES[obj.type].needs_services:
                return False, f"Object {obj.id} ({obj.type}) relies on the service to be removed: {req.args.id}."

        srv = glob.SCENE.service(req.args.id)
        glob.SCENE.services = [srv for srv in glob.SCENE.services if srv.type != req.args.id]
        del glob.SERVICES_INSTANCES[req.args.id]
        asyncio.ensure_future(notif.broadcast_event(events.SceneServiceChanged(events.EventType.REMOVE, data=srv)))

    else:
        return False, "Unknown id."

    glob.SCENE.last_modified = datetime.now()
    asyncio.ensure_future(remove_object_references_from_projects(req.args.id))
    return None


@scene_needed
@no_project
async def update_object_pose_using_robot_cb(req: rpc.objects.UpdateObjectPoseUsingRobotRequest) -> \
        Union[rpc.objects.UpdateObjectPoseUsingRobotResponse, hlp.RPC_RETURN_TYPES]:
    """
    Updates object's pose using a pose of the robot's end effector.
    :param req:
    :return:
    """

    assert glob.SCENE

    if req.args.id == req.args.robot.robot_id:
        return False, "Robot cannot update its own pose."

    try:
        scene_object = glob.SCENE.object(req.args.id)
    except Arcor2Exception as e:
        return False, str(e)

    try:
        scene_object.pose = await get_end_effector_pose(req.args.robot.robot_id, req.args.robot.end_effector)
    except RobotPoseException as e:
        return False, str(e)

    glob.SCENE.last_modified = datetime.now()
    asyncio.ensure_future(notif.broadcast_event(events.SceneObjectChanged(events.EventType.UPDATE, data=scene_object)))
    return None


@scene_needed
@no_project
async def update_object_pose_cb(req: rpc.scene.UpdateObjectPoseRequest) -> \
        Union[rpc.scene.UpdateObjectPoseResponse, hlp.RPC_RETURN_TYPES]:

    assert glob.SCENE

    obj = glob.SCENE.object(req.args.object_id)
    obj.pose = req.args.pose
    glob.SCENE.last_modified = datetime.now()
    asyncio.ensure_future(notif.broadcast_event(events.SceneObjectChanged(events.EventType.UPDATE, data=obj)))
    return None


@scene_needed
@no_project
async def rename_object_cb(req: rpc.scene.RenameObjectRequest) -> \
        Union[rpc.scene.RenameObjectResponse, hlp.RPC_RETURN_TYPES]:

    assert glob.SCENE

    target_obj = glob.SCENE.object(req.args.id)

    for obj in glob.SCENE.objects:

        if obj.user_id == req.args.new_user_id:
            return False, f"User_id already exists."

    target_obj.user_id = req.args.new_user_id

    glob.SCENE.last_modified = datetime.now()
    asyncio.ensure_future(notif.broadcast_event(events.SceneObjectChanged(events.EventType.UPDATE, data=target_obj)))
    return None


async def rename_scene_cb(req: rpc.scene.RenameSceneRequest) -> \
        Union[rpc.scene.RenameSceneResponse, hlp.RPC_RETURN_TYPES]:

    save_back = False

    if glob.SCENE and glob.SCENE.id == req.args.id:
        scene = glob.SCENE
    else:
        try:
            scene = await storage.get_scene(req.args.id)
        except storage.PersistentStorageException as e:
            return False, str(e)
        save_back = True

    scene.last_modified = datetime.now()
    scene.user_id = req.args.new_user_id

    if save_back:
        asyncio.ensure_future(storage.update_scene(scene))

    asyncio.ensure_future(notif.broadcast_event(events.SceneChanged(events.EventType.UPDATE, data=scene)))
    return None


@no_scene
async def delete_scene_cb(req: rpc.scene.DeleteSceneRequest) -> \
        Union[rpc.scene.DeleteSceneResponse, hlp.RPC_RETURN_TYPES]:

    associated_projects = {project.id async for project in projects(req.args.id)}

    if associated_projects:
        resp = rpc.scene.DeleteSceneResponse(result=False)
        resp.messages = ["Scene has associated projects."]
        resp.data = associated_projects
        return resp

    # TODO implement delete_scene in storage module
    return None


async def projects_with_scene_cb(req: rpc.scene.ProjectsWithSceneRequest) -> \
        Union[rpc.scene.ProjectsWithSceneResponse, hlp.RPC_RETURN_TYPES]:

    resp = rpc.scene.ProjectsWithSceneResponse()
    resp.data = {project.id async for project in projects(req.args.id)}
    return resp
