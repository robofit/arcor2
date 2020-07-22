#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import asyncio
import copy
import functools
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional, Set

import quaternion  # type: ignore

from websockets.server import WebSocketServerProtocol as WsClient

from arcor2 import helpers as hlp
from arcor2.cached import UpdateableCachedScene
from arcor2.clients import aio_persistent_storage as storage, aio_scene_service as scene_srv
from arcor2.data import common, object_type
from arcor2.data import events, rpc
from arcor2.exceptions import Arcor2Exception
from arcor2.object_types.abstract import GenericWithPose
from arcor2.server import globals as glob, notifications as notif
from arcor2.server.decorators import no_project, no_scene, scene_needed
from arcor2.server.helpers import unique_name
from arcor2.server.project import associated_projects, projects_using_object, remove_object_references_from_projects, \
    scene_object_pose_updated
from arcor2.server.robot import get_end_effector_pose
from arcor2.server.scene import add_object_to_scene, clear_scene, \
    get_instance, open_scene, scene_names, scenes, set_object_pose

OBJECTS_WITH_UPDATED_POSE: Set[str] = set()


@asynccontextmanager
async def managed_scene(scene_id: str, make_copy: bool = False) -> AsyncGenerator[UpdateableCachedScene, None]:

    save_back = False

    if glob.SCENE and glob.SCENE.id == scene_id:
        if make_copy:
            scene = copy.deepcopy(glob.SCENE)
            save_back = True
        else:
            scene = glob.SCENE
    else:
        save_back = True
        scene = UpdateableCachedScene(await storage.get_scene(scene_id))

    if make_copy:
        scene.id = common.uid()

    try:
        yield scene
    finally:
        if save_back:
            asyncio.ensure_future(storage.update_scene(scene.scene))


@no_scene
async def new_scene_cb(req: rpc.scene.NewSceneRequest, ui: WsClient) -> None:
    """
    Creates and opens a new scene on the server. Fails if any scene is open or if scene id/name already exists.
    :param req:
    :return:
    """

    if glob.PACKAGE_STATE.state in (common.PackageStateEnum.PAUSED, common.PackageStateEnum.RUNNING):
        raise Arcor2Exception("Can't create scene while package runs.")

    assert glob.SCENE is None

    for scene_id in (await storage.get_scenes()).items:
        if req.args.name == scene_id.name:
            raise Arcor2Exception("Name already used.")

    if req.dry_run:
        return None

    glob.SCENE = UpdateableCachedScene(common.Scene(common.uid(), req.args.name, desc=req.args.desc))
    asyncio.ensure_future(notif.broadcast_event(events.OpenScene(data=events.OpenSceneData(glob.SCENE.scene))))
    asyncio.ensure_future(scene_srv.delete_all_collisions())  # just for sure
    return None


async def notify_scene_closed(scene_id: str) -> None:

    await notif.broadcast_event(events.SceneClosed())
    glob.MAIN_SCREEN = events.ShowMainScreenData(events.ShowMainScreenData.WhatEnum.ScenesList)
    await notif.broadcast_event(events.ShowMainScreenEvent(
        data=events.ShowMainScreenData(events.ShowMainScreenData.WhatEnum.ScenesList, scene_id)))


@scene_needed
@no_project
async def close_scene_cb(req: rpc.scene.CloseSceneRequest, ui: WsClient) -> None:
    """
    Closes scene on the server.
    :param req:
    :return:
    """

    assert glob.SCENE

    if not req.args.force and glob.SCENE.has_changes():
        raise Arcor2Exception("Scene has unsaved changes.")

    if req.dry_run:
        return None

    scene_id = glob.SCENE.id

    await clear_scene()
    OBJECTS_WITH_UPDATED_POSE.clear()
    asyncio.ensure_future(notify_scene_closed(scene_id))


@scene_needed
@no_project
async def save_scene_cb(req: rpc.scene.SaveSceneRequest, ui: WsClient) -> None:

    assert glob.SCENE
    await storage.update_scene(glob.SCENE.scene)
    glob.SCENE.modified = (await storage.get_scene(glob.SCENE.id)).modified
    asyncio.ensure_future(notif.broadcast_event(events.SceneSaved()))
    for obj_id in OBJECTS_WITH_UPDATED_POSE:
        asyncio.ensure_future(scene_object_pose_updated(glob.SCENE.id, obj_id))
    OBJECTS_WITH_UPDATED_POSE.clear()
    return None


@no_project
async def open_scene_cb(req: rpc.scene.OpenSceneRequest, ui: WsClient) -> None:

    if glob.PACKAGE_STATE.state in (common.PackageStateEnum.PAUSED, common.PackageStateEnum.RUNNING):
        raise Arcor2Exception("Can't open scene while package runs.")

    await open_scene(req.args.id)
    assert glob.SCENE
    asyncio.ensure_future(notif.broadcast_event(events.OpenScene(data=events.OpenSceneData(glob.SCENE.scene))))
    return None


async def list_scenes_cb(req: rpc.scene.ListScenesRequest, ui: WsClient) -> rpc.scene.ListScenesResponse:

    resp = rpc.scene.ListScenesResponse()

    async for scene in scenes():
        resp.data.append(rpc.scene.ListScenesResponseData(scene.id, scene.name, scene.desc, scene.modified))

    return resp


@scene_needed
@no_project
async def add_object_to_scene_cb(req: rpc.scene.AddObjectToSceneRequest, ui: WsClient) -> None:

    assert glob.SCENE

    obj = common.SceneObject(common.uid(), req.args.name, req.args.type, req.args.pose, req.args.settings)

    await add_object_to_scene(obj, dry_run=req.dry_run)

    if req.dry_run:
        return None

    glob.SCENE.update_modified()
    asyncio.ensure_future(notif.broadcast_event(events.SceneObjectChanged(events.EventType.ADD, data=obj)))
    return None


@scene_needed
async def scene_object_usage_request_cb(req: rpc.scene.SceneObjectUsageRequest, ui: WsClient) -> \
        rpc.scene.SceneObjectUsageResponse:
    """
    Works for both services and objects.
    :param req:
    :return:
    """

    assert glob.SCENE

    if not (any(obj.id == req.args.id for obj in glob.SCENE.objects)):
        raise Arcor2Exception("Unknown ID.")

    resp = rpc.scene.SceneObjectUsageResponse()

    async for project in projects_using_object(glob.SCENE.id, req.args.id):
        resp.data.add(project.id)

    return resp


# TODO move to objects
@scene_needed
async def action_param_values_cb(req: rpc.objects.ActionParamValuesRequest, ui: WsClient) -> \
        rpc.objects.ActionParamValuesResponse:

    inst = get_instance(req.args.id)

    parent_params = {}

    for pp in req.args.parent_params:
        parent_params[pp.id] = pp.value

    try:
        method_name, required_parent_params = inst.DYNAMIC_PARAMS[req.args.param_id]
    except KeyError:
        raise Arcor2Exception("Unknown parameter or values not constrained.")

    if parent_params.keys() != required_parent_params:
        raise Arcor2Exception("Not all required parent params were given.")

    # TODO validate method parameters vs parent_params (check types)?

    resp = rpc.objects.ActionParamValuesResponse()

    try:
        method = getattr(inst, method_name)
    except AttributeError:
        await glob.logger.error(f"Unable to get values for parameter {req.args.param_id}, "
                                f"object/service {inst.id} has no method named {method_name}.")
        raise Arcor2Exception("System error.")

    # TODO update hlp.run_in_executor to support kwargs
    resp.data = await asyncio.get_event_loop().run_in_executor(None, functools.partial(method, **parent_params))
    return resp


@scene_needed
@no_project
async def remove_from_scene_cb(req: rpc.scene.RemoveFromSceneRequest, ui: WsClient) -> None:

    assert glob.SCENE

    if not req.args.force and {proj.name async for proj in projects_using_object(glob.SCENE.id, req.args.id)}:
        raise Arcor2Exception("Can't remove object that is used in project(s).")

    if req.dry_run:
        return None

    if req.args.id not in glob.SCENE_OBJECT_INSTANCES:
        raise Arcor2Exception("Unknown id.")

    obj = glob.SCENE.object(req.args.id)
    glob.SCENE.delete_object(req.args.id)
    obj_inst = glob.SCENE_OBJECT_INSTANCES[req.args.id]

    del glob.SCENE_OBJECT_INSTANCES[req.args.id]
    if req.args.id in OBJECTS_WITH_UPDATED_POSE:
        OBJECTS_WITH_UPDATED_POSE.remove(req.args.id)
    asyncio.ensure_future(notif.broadcast_event(events.SceneObjectChanged(events.EventType.REMOVE, data=obj)))
    asyncio.ensure_future(remove_object_references_from_projects(req.args.id))
    asyncio.ensure_future(hlp.run_in_executor(obj_inst.cleanup))
    return None


@scene_needed
@no_project
async def update_object_pose_using_robot_cb(req: rpc.objects.UpdateObjectPoseUsingRobotRequest, ui: WsClient) -> \
        None:
    """
    Updates object's pose using a pose of the robot's end effector.
    :param req:
    :return:
    """

    assert glob.SCENE

    if req.args.id == req.args.robot.robot_id:
        raise Arcor2Exception("Robot cannot update its own pose.")

    scene_object = glob.SCENE.object(req.args.id)

    obj_inst = glob.SCENE_OBJECT_INSTANCES[req.args.id]

    if not isinstance(obj_inst, GenericWithPose):
        raise Arcor2Exception("Object without pose.")

    if obj_inst.collision_model:
        if isinstance(obj_inst.collision_model, object_type.Mesh) and req.args.pivot != rpc.objects.PivotEnum.MIDDLE:
            raise Arcor2Exception("Only middle pivot point is supported for objects with mesh collision model.")
    elif req.args.pivot != rpc.objects.PivotEnum.MIDDLE:
        raise Arcor2Exception("Only middle pivot point is supported for objects without collision model.")

    new_pose = await get_end_effector_pose(req.args.robot.robot_id, req.args.robot.end_effector)

    position_delta = common.Position()

    if obj_inst.collision_model:
        if isinstance(obj_inst.collision_model, object_type.Box):
            if req.args.pivot == rpc.objects.PivotEnum.TOP:
                position_delta.z -= obj_inst.collision_model.size_z / 2
            elif req.args.pivot == rpc.objects.PivotEnum.BOTTOM:
                position_delta.z += obj_inst.collision_model.size_z / 2
        elif isinstance(obj_inst.collision_model, object_type.Cylinder):
            if req.args.pivot == rpc.objects.PivotEnum.TOP:
                position_delta.z -= obj_inst.collision_model.height / 2
            elif req.args.pivot == rpc.objects.PivotEnum.BOTTOM:
                position_delta.z += obj_inst.collision_model.height / 2
        elif isinstance(obj_inst.collision_model, object_type.Sphere):
            if req.args.pivot == rpc.objects.PivotEnum.TOP:
                position_delta.z -= obj_inst.collision_model.radius / 2
            elif req.args.pivot == rpc.objects.PivotEnum.BOTTOM:
                position_delta.z += obj_inst.collision_model.radius / 2

    position_delta = position_delta.rotated(new_pose.orientation)

    assert scene_object.pose

    scene_object.pose.position.x = new_pose.position.x - position_delta.x
    scene_object.pose.position.y = new_pose.position.y - position_delta.y
    scene_object.pose.position.z = new_pose.position.z - position_delta.z

    scene_object.pose.orientation.set_from_quaternion(
        new_pose.orientation.as_quaternion() * quaternion.quaternion(0, 1, 0, 0))

    glob.SCENE.update_modified()
    asyncio.ensure_future(notif.broadcast_event(events.SceneObjectChanged(events.EventType.UPDATE, data=scene_object)))
    OBJECTS_WITH_UPDATED_POSE.add(scene_object.id)
    asyncio.ensure_future(set_object_pose(obj_inst, scene_object.pose))

    return None


@scene_needed
@no_project
async def update_object_pose_cb(req: rpc.scene.UpdateObjectPoseRequest, ui: WsClient) -> None:

    assert glob.SCENE

    obj = glob.SCENE.object(req.args.object_id)

    if not obj.pose:
        raise Arcor2Exception("Object without pose.")

    obj.pose = req.args.pose

    obj_inst = glob.SCENE_OBJECT_INSTANCES[req.args.object_id]
    assert isinstance(obj_inst, GenericWithPose)

    glob.SCENE.update_modified()
    asyncio.ensure_future(notif.broadcast_event(events.SceneObjectChanged(events.EventType.UPDATE, data=obj)))
    OBJECTS_WITH_UPDATED_POSE.add(obj.id)
    asyncio.ensure_future(set_object_pose(obj_inst, obj.pose))

    return None


@scene_needed
@no_project
async def rename_object_cb(req: rpc.scene.RenameObjectRequest, ui: WsClient) -> None:

    assert glob.SCENE

    target_obj = glob.SCENE.object(req.args.id)

    for obj_name in glob.SCENE.object_names():
        if obj_name == req.args.new_name:
            raise Arcor2Exception("Object name already exists.")

    if not hlp.is_valid_identifier(req.args.new_name):
        raise Arcor2Exception("Object name invalid (should be snake_case).")

    if req.dry_run:
        return None

    target_obj.name = req.args.new_name

    glob.SCENE.update_modified()
    asyncio.ensure_future(notif.broadcast_event(events.SceneObjectChanged(events.EventType.UPDATE, data=target_obj)))
    return None


async def rename_scene_cb(req: rpc.scene.RenameSceneRequest, ui: WsClient) -> None:

    unique_name(req.args.new_name, (await scene_names()))

    if req.dry_run:
        return None

    async with managed_scene(req.args.id) as scene:
        scene.name = req.args.new_name
        asyncio.ensure_future(notif.broadcast_event(events.SceneChanged(events.EventType.UPDATE_BASE,
                                                                        data=scene.bare)))
    return None


@no_scene
async def delete_scene_cb(req: rpc.scene.DeleteSceneRequest, ui: WsClient) -> \
        Optional[rpc.scene.DeleteSceneResponse]:

    assoc_projects = await associated_projects(req.args.id)

    if assoc_projects:
        resp = rpc.scene.DeleteSceneResponse(result=False)
        resp.messages = ["Scene has associated projects."]
        resp.data = assoc_projects
        return resp

    if req.dry_run:
        return None

    scene = UpdateableCachedScene(await storage.get_scene(req.args.id))
    await storage.delete_scene(req.args.id)
    asyncio.ensure_future(notif.broadcast_event(events.SceneChanged(events.EventType.REMOVE,
                                                                    data=scene.bare)))
    return None


async def projects_with_scene_cb(req: rpc.scene.ProjectsWithSceneRequest, ui: WsClient) -> \
        rpc.scene.ProjectsWithSceneResponse:

    resp = rpc.scene.ProjectsWithSceneResponse()
    resp.data = await associated_projects(req.args.id)
    return resp


async def update_scene_description_cb(req: rpc.scene.UpdateSceneDescriptionRequest, ui: WsClient) -> None:

    async with managed_scene(req.args.scene_id) as scene:
        scene.desc = req.args.new_description
        scene.update_modified()
        asyncio.ensure_future(notif.broadcast_event(events.SceneChanged(events.EventType.UPDATE_BASE,
                                                                        data=scene.bare)))
    return None


async def copy_scene_cb(req: rpc.scene.CopySceneRequest, ui: WsClient) -> None:

    # TODO check if target_name is unique
    async with managed_scene(req.args.source_id, make_copy=True) as scene:
        scene.name = req.args.target_name
        asyncio.ensure_future(notif.broadcast_event(events.SceneChanged(events.EventType.UPDATE_BASE,
                                                                        data=scene.bare)))

    return None
