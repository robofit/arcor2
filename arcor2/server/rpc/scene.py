#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from typing import Union, Set
import asyncio
import functools
from contextlib import asynccontextmanager
import copy

import quaternion  # type: ignore

from arcor2 import aio_persistent_storage as storage, helpers as hlp
from arcor2.data import rpc, events
from arcor2.data import common, object_type
from arcor2.object_types import Generic
from arcor2.services import Service

from arcor2.server.robot import get_end_effector_pose
from arcor2.server.decorators import scene_needed, no_project, no_scene
from arcor2.server import globals as glob, notifications as notif
from arcor2.server.robot import collision
from arcor2.server.scene import add_object_to_scene, auto_add_object_to_scene, open_scene, add_service_to_scene,\
    clear_scene
from arcor2.server.project import scene_object_pose_updated, remove_object_references_from_projects,\
    projects_using_object, associated_projects


OBJECTS_WITH_UPDATED_POSE: Set[str] = set()


@asynccontextmanager
async def managed_scene(scene_id: str, make_copy: bool = False):

    save_back = False

    if glob.SCENE and glob.SCENE.id == scene_id:
        if make_copy:
            scene = copy.deepcopy(glob.SCENE)
            save_back = True
        else:
            scene = glob.SCENE
    else:
        save_back = True
        scene = await storage.get_scene(scene_id)

    if make_copy:
        scene.id = common.uid()

    try:
        yield scene
    finally:
        if save_back:
            asyncio.ensure_future(storage.update_scene(scene))


@no_scene
async def new_scene_cb(req: rpc.scene.NewSceneRequest) -> Union[rpc.scene.NewSceneResponse,
                                                                hlp.RPC_RETURN_TYPES]:
    """
    Creates and opens a new scene on the server. Fails if any scene is open or if scene id/name already exists.
    :param req:
    :return:
    """

    assert glob.SCENE is None

    for scene_id in (await storage.get_scenes()).items:
        if req.args.name == scene_id.name:
            return False, "Name already used."

    glob.SCENE = common.Scene(common.uid(), req.args.name, desc=req.args.desc)
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

    if not req.args.force and glob.SCENE.has_changes():
        return False, "Scene has unsaved changes."

    await clear_scene()
    OBJECTS_WITH_UPDATED_POSE.clear()
    asyncio.ensure_future(notif.broadcast_event(events.SceneChanged(events.EventType.UPDATE)))
    return None


@scene_needed
@no_project
async def save_scene_cb(req: rpc.scene.SaveSceneRequest) -> Union[rpc.scene.SaveSceneResponse,
                                                                  hlp.RPC_RETURN_TYPES]:

    assert glob.SCENE
    await storage.update_scene(glob.SCENE)
    glob.SCENE.modified = (await storage.get_scene(glob.SCENE.id)).modified
    asyncio.ensure_future(notif.broadcast_event(events.SceneSaved()))
    for obj_id in OBJECTS_WITH_UPDATED_POSE:
        asyncio.ensure_future(scene_object_pose_updated(glob.SCENE.id, obj_id))
    OBJECTS_WITH_UPDATED_POSE.clear()
    return None


@no_project
async def open_scene_cb(req: rpc.scene.OpenSceneRequest) -> Union[rpc.scene.OpenSceneResponse,
                                                                  hlp.RPC_RETURN_TYPES]:

    await open_scene(req.args.id)
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

    obj = common.SceneObject(common.uid(), req.args.name, req.args.type, req.args.pose)

    res, msg = await add_object_to_scene(obj)

    if not res:
        return res, msg

    glob.SCENE.update_modified()
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

    glob.SCENE.update_modified()
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
    glob.SCENE.update_modified()
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


# TODO move to objects
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

    if not req.args.force and {proj.name async for proj in projects_using_object(glob.SCENE.id, req.args.id)}:
        return False, "Can't remove object/service that is used in project(s)."

    if req.args.id in glob.SCENE_OBJECT_INSTANCES:

        obj = glob.SCENE.object(req.args.id)
        glob.SCENE.objects = [obj for obj in glob.SCENE.objects if obj.id != req.args.id]
        obj_inst = glob.SCENE_OBJECT_INSTANCES[req.args.id]
        await collision(obj_inst, remove=True)
        del glob.SCENE_OBJECT_INSTANCES[req.args.id]
        if req.args.id in OBJECTS_WITH_UPDATED_POSE:
            OBJECTS_WITH_UPDATED_POSE.remove(req.args.id)
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

    glob.SCENE.update_modified()
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

    scene_object = glob.SCENE.object(req.args.id)

    if glob.OBJECT_TYPES[scene_object.type].needs_services:
        return False, "Can't manipulate object created by service."

    obj_inst = glob.SCENE_OBJECT_INSTANCES[req.args.id]

    if obj_inst.collision_model:
        if isinstance(obj_inst.collision_model, object_type.Mesh) and req.args.pivot != rpc.objects.PivotEnum.MIDDLE:
            return False, "Only middle pivot point is supported for objects with mesh collision model."
    elif req.args.pivot != rpc.objects.PivotEnum.MIDDLE:
        return False, "Only middle pivot point is supported for objects without collision model."

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

    scene_object.pose.position.x = new_pose.position.x - position_delta.x
    scene_object.pose.position.y = new_pose.position.y - position_delta.y
    scene_object.pose.position.z = new_pose.position.z - position_delta.z

    scene_object.pose.orientation.set_from_quaternion(
        new_pose.orientation.as_quaternion()*quaternion.quaternion(0, 1, 0, 0))

    glob.SCENE.update_modified()
    asyncio.ensure_future(notif.broadcast_event(events.SceneObjectChanged(events.EventType.UPDATE, data=scene_object)))
    OBJECTS_WITH_UPDATED_POSE.add(scene_object.id)
    return None


@scene_needed
@no_project
async def update_object_pose_cb(req: rpc.scene.UpdateObjectPoseRequest) -> \
        Union[rpc.scene.UpdateObjectPoseResponse, hlp.RPC_RETURN_TYPES]:

    assert glob.SCENE

    obj = glob.SCENE.object(req.args.object_id)

    if glob.OBJECT_TYPES[obj.type].needs_services:
        return False, "Can't manipulate object created by service."

    obj.pose = req.args.pose

    glob.SCENE.update_modified()
    asyncio.ensure_future(notif.broadcast_event(events.SceneObjectChanged(events.EventType.UPDATE, data=obj)))

    OBJECTS_WITH_UPDATED_POSE.add(obj.id)
    return None


@scene_needed
@no_project
async def rename_object_cb(req: rpc.scene.RenameObjectRequest) -> \
        Union[rpc.scene.RenameObjectResponse, hlp.RPC_RETURN_TYPES]:

    assert glob.SCENE

    target_obj = glob.SCENE.object(req.args.id)

    for obj_name in glob.SCENE.object_names():
        if obj_name == req.args.new_name:
            return False, "Object name already exists."

    target_obj.name = req.args.new_name

    glob.SCENE.update_modified()
    asyncio.ensure_future(notif.broadcast_event(events.SceneObjectChanged(events.EventType.UPDATE, data=target_obj)))
    return None


async def rename_scene_cb(req: rpc.scene.RenameSceneRequest) -> \
        Union[rpc.scene.RenameSceneResponse, hlp.RPC_RETURN_TYPES]:

    async with managed_scene(req.args.id) as scene:
        scene.name = req.args.new_name
        asyncio.ensure_future(notif.broadcast_event(events.SceneChanged(events.EventType.UPDATE_BASE,
                                                                        data=scene.bare())))
    return None


@no_scene
async def delete_scene_cb(req: rpc.scene.DeleteSceneRequest) -> \
        Union[rpc.scene.DeleteSceneResponse, hlp.RPC_RETURN_TYPES]:

    assoc_projects = await associated_projects(req.args.id)

    if assoc_projects:
        resp = rpc.scene.DeleteSceneResponse(result=False)
        resp.messages = ["Scene has associated projects."]
        resp.data = assoc_projects
        return resp

    scene = await storage.get_scene(req.args.id)
    await storage.delete_scene(req.args.id)
    asyncio.ensure_future(notif.broadcast_event(events.SceneChanged(events.EventType.REMOVE,
                                                                    data=scene.bare())))
    return None


async def projects_with_scene_cb(req: rpc.scene.ProjectsWithSceneRequest) -> \
        Union[rpc.scene.ProjectsWithSceneResponse, hlp.RPC_RETURN_TYPES]:

    resp = rpc.scene.ProjectsWithSceneResponse()
    resp.data = await associated_projects(req.args.id)
    return resp


async def update_scene_description_cb(req: rpc.scene.UpdateSceneDescriptionRequest) -> \
        Union[rpc.scene.UpdateSceneDescriptionResponse, hlp.RPC_RETURN_TYPES]:

    async with managed_scene(req.args.scene_id) as scene:
        scene.desc = req.args.new_description
        scene.update_modified()
        asyncio.ensure_future(notif.broadcast_event(events.SceneChanged(events.EventType.UPDATE_BASE,
                                                                        data=scene.bare())))
    return None


@scene_needed
async def update_service_configuration_cb(req: rpc.scene.UpdateServiceConfigurationRequest) -> \
        Union[rpc.scene.UpdateServiceConfigurationResponse, hlp.RPC_RETURN_TYPES]:

    assert glob.SCENE

    srv = glob.SCENE.service(req.args.type)

    # first check if some object is not using it
    for obj in glob.SCENE.objects:
        if req.args.type in glob.OBJECT_TYPES[obj.type].needs_services:
            return False, f"Object {obj.name} ({obj.type}) relies on the service to be removed: {req.args.type}."

    # TODO destroy current instance
    glob.SERVICES_INSTANCES[req.args.type] = await hlp.run_in_executor(glob.TYPE_DEF_DICT[req.args.type],
                                                                       req.args.new_configuration)
    srv.configuration_id = req.args.new_configuration

    glob.SCENE.update_modified()
    asyncio.ensure_future(notif.broadcast_event(events.SceneServiceChanged(events.EventType.UPDATE, data=srv)))

    return None


async def copy_scene_cb(req: rpc.scene.CopySceneRequest) -> \
        Union[rpc.scene.CopySceneResponse, hlp.RPC_RETURN_TYPES]:

    async with managed_scene(req.args.source_id, make_copy=True) as scene:
        scene.name = req.args.target_name
        asyncio.ensure_future(notif.broadcast_event(events.SceneChanged(events.EventType.UPDATE_BASE,
                                                                        data=scene.bare())))

    return None
