#!/usr/bin/env python3
# -*- coding: utf-8 -*-


import asyncio
from typing import Dict, List

from websockets.server import WebSocketServerProtocol as WsClient

from arcor2 import helpers as hlp
from arcor2.cached import CachedScene
from arcor2.clients import aio_scene_service as scene_srv
from arcor2.data import events, rpc
from arcor2.data.common import Pose, Position
from arcor2.data.object_type import MeshFocusAction, Model3dType
from arcor2.exceptions import Arcor2Exception
from arcor2.object_types import utils as otu
from arcor2.object_types.abstract import GenericWithPose, Robot
from arcor2.server import globals as glob, notifications as notif, objects_actions as osa, settings
from arcor2.server.clients import persistent_storage as storage
from arcor2.server.decorators import no_project, scene_needed
from arcor2.server.project import scene_object_pose_updated
from arcor2.server.robot import get_end_effector_pose
from arcor2.server.scene import scenes, set_object_pose
from arcor2.source.object_types import new_object_type
from arcor2.source.utils import tree_to_str

FOCUS_OBJECT: Dict[str, Dict[int, Pose]] = {}  # object_id / idx, pose
FOCUS_OBJECT_ROBOT: Dict[str, rpc.common.RobotArg] = {}  # key: object_id


def clean_up_after_focus(obj_id: str) -> None:

    try:
        del FOCUS_OBJECT[obj_id]
    except KeyError:
        pass

    try:
        del FOCUS_OBJECT_ROBOT[obj_id]
    except KeyError:
        pass


@scene_needed
@no_project
async def focus_object_start_cb(req: rpc.objects.FocusObjectStartRequest, ui: WsClient) -> None:

    obj_id = req.args.object_id

    if obj_id in FOCUS_OBJECT_ROBOT:
        raise Arcor2Exception("Focusing already started.")

    if obj_id not in glob.SCENE_OBJECT_INSTANCES:
        raise Arcor2Exception("Unknown object.")

    inst = await osa.get_robot_instance(req.args.robot.robot_id, req.args.robot.end_effector)

    robot_type = glob.OBJECT_TYPES[inst.__class__.__name__]
    assert robot_type.robot_meta

    obj_type = glob.OBJECT_TYPES[osa.get_obj_type_name(obj_id)].meta

    if not obj_type.has_pose:
        raise Arcor2Exception("Only available for objects with pose.")

    if not obj_type.object_model or obj_type.object_model.type != Model3dType.MESH:
        raise Arcor2Exception("Only available for objects with mesh model.")

    assert obj_type.object_model.mesh

    focus_points = obj_type.object_model.mesh.focus_points

    if not focus_points:
        raise Arcor2Exception("focusPoints not defined for the mesh.")

    FOCUS_OBJECT_ROBOT[req.args.object_id] = req.args.robot
    FOCUS_OBJECT[obj_id] = {}
    glob.logger.info(f'Start of focusing for {obj_id}.')
    return None


@no_project
async def focus_object_cb(req: rpc.objects.FocusObjectRequest, ui: WsClient) -> rpc.objects.FocusObjectResponse:

    obj_id = req.args.object_id
    pt_idx = req.args.point_idx

    if obj_id not in glob.SCENE_OBJECT_INSTANCES:
        raise Arcor2Exception("Unknown object_id.")

    obj_type = glob.OBJECT_TYPES[osa.get_obj_type_name(obj_id)].meta

    assert obj_type.has_pose
    assert obj_type.object_model
    assert obj_type.object_model.mesh

    focus_points = obj_type.object_model.mesh.focus_points

    assert focus_points

    if pt_idx < 0 or pt_idx > len(focus_points) - 1:
        raise Arcor2Exception("Index out of range.")

    if obj_id not in FOCUS_OBJECT:
        glob.logger.info(f'Start of focusing for {obj_id}.')
        FOCUS_OBJECT[obj_id] = {}

    robot_id, end_effector = FOCUS_OBJECT_ROBOT[obj_id].as_tuple()

    FOCUS_OBJECT[obj_id][pt_idx] = await get_end_effector_pose(robot_id, end_effector)

    r = rpc.objects.FocusObjectResponse()
    r.data.finished_indexes = list(FOCUS_OBJECT[obj_id].keys())
    return r


@scene_needed
@no_project
async def focus_object_done_cb(req: rpc.objects.FocusObjectDoneRequest, ui: WsClient) -> None:

    obj_id = req.args.id

    if obj_id not in FOCUS_OBJECT:
        raise Arcor2Exception("focusObjectStart/focusObject has to be called first.")

    obj_type = glob.OBJECT_TYPES[osa.get_obj_type_name(obj_id)].meta

    assert obj_type.object_model
    assert obj_type.object_model.mesh

    focus_points = obj_type.object_model.mesh.focus_points

    assert focus_points

    if len(FOCUS_OBJECT[obj_id]) < len(focus_points):
        raise Arcor2Exception("Not all points were done.")

    assert glob.SCENE

    obj = glob.SCENE.object(obj_id)
    assert obj.pose

    obj_inst = glob.SCENE_OBJECT_INSTANCES[obj_id]
    assert isinstance(obj_inst, GenericWithPose)

    fp: List[Position] = []
    rp: List[Position] = []

    for idx, pose in FOCUS_OBJECT[obj_id].items():

        fp.append(focus_points[idx].position)
        rp.append(pose.position)

    mfa = MeshFocusAction(fp, rp)

    glob.logger.debug(f'Attempt to focus for object {obj_id}, data: {mfa}')

    try:
        new_pose = await scene_srv.focus(mfa)
    except scene_srv.SceneServiceException as e:
        glob.logger.error(f"Focus failed with: {e}, mfa: {mfa}.")
        raise Arcor2Exception("Focusing failed.") from e

    obj.pose = new_pose
    glob.SCENE.update_modified()

    glob.logger.info(f"Done focusing for {obj_id}.")

    clean_up_after_focus(obj_id)

    asyncio.ensure_future(notif.broadcast_event(events.SceneObjectChanged(events.EventType.UPDATE, data=obj)))
    asyncio.ensure_future(scene_object_pose_updated(glob.SCENE.id, obj.id))
    asyncio.ensure_future(set_object_pose(obj_inst, new_pose))

    return None


async def new_object_type_cb(req: rpc.objects.NewObjectTypeRequest, ui: WsClient) -> None:

    meta = req.args

    if meta.type in glob.OBJECT_TYPES:
        raise Arcor2Exception("Object type already exists.")

    if not hlp.is_valid_type(meta.type):
        raise Arcor2Exception("Object type invalid (should be CamelCase).")

    if meta.base not in glob.OBJECT_TYPES:
        raise Arcor2Exception(f"Unknown base object type '{meta.base}', "
                              f"known types are: {', '.join(glob.OBJECT_TYPES.keys())}.")

    base = glob.OBJECT_TYPES[meta.base]

    if base.meta.disabled:
        raise Arcor2Exception("Base object is disabled.")

    assert base.type_def is not None

    if issubclass(base.type_def, Robot):
        raise Arcor2Exception("Can't subclass Robot.")

    meta.has_pose = issubclass(base.type_def, GenericWithPose)

    if not meta.has_pose and meta.object_model:
        raise Arcor2Exception("Object without pose can't have collision model.")

    if req.dry_run:
        return None

    obj = meta.to_object_type()
    ast = new_object_type(glob.OBJECT_TYPES[meta.base].meta, meta)
    obj.source = tree_to_str(ast)

    if meta.object_model and meta.object_model.type != Model3dType.MESH:
        assert meta.type == meta.object_model.model().id
        await storage.put_model(meta.object_model.model())

    # TODO check whether mesh id exists - if so, then use existing mesh, if not, upload a new one
    if meta.object_model and meta.object_model.type == Model3dType.MESH:
        # ...get whole mesh (focus_points) based on mesh id
        assert meta.object_model.mesh
        try:
            meta.object_model.mesh = await storage.get_mesh(meta.object_model.mesh.id)
        except storage.PersistentStorageException as e:
            glob.logger.error(e)
            raise Arcor2Exception(f"Mesh ID {meta.object_model.mesh.id} does not exist.")

    type_def = await hlp.run_in_executor(
        hlp.save_and_import_type_def, obj.source, obj.id, base.type_def, settings.OBJECT_TYPE_PATH,
        settings.OBJECT_TYPE_MODULE)
    assert issubclass(type_def, base.type_def)
    actions = otu.object_actions(type_def, ast)

    await storage.update_object_type(obj)

    glob.OBJECT_TYPES[meta.type] = otu.ObjectTypeData(meta, type_def, actions, ast)
    otu.add_ancestor_actions(meta.type, glob.OBJECT_TYPES)

    asyncio.ensure_future(notif.broadcast_event(events.ChangedObjectTypesEvent(events.EventType.ADD, data=[meta])))
    return None


async def get_object_actions_cb(req: rpc.objects.GetActionsRequest, ui: WsClient) -> rpc.objects.GetActionsResponse:

    try:
        return rpc.objects.GetActionsResponse(data=list(glob.OBJECT_TYPES[req.args.type].actions.values()))
    except KeyError:
        raise Arcor2Exception(f"Unknown object type: '{req.args.type}'.")


async def get_object_types_cb(req: rpc.objects.GetObjectTypesRequest, ui: WsClient) ->\
        rpc.objects.GetObjectTypesResponse:
    return rpc.objects.GetObjectTypesResponse(data=[obj.meta for obj in glob.OBJECT_TYPES.values()])


def check_scene_for_object_type(scene: CachedScene, object_type: str) -> None:

    if list(scene.objects_of_type(object_type)):
        raise Arcor2Exception(f"Object type used in scene '{scene.name}'.")


async def delete_object_type_cb(req: rpc.objects.DeleteObjectTypeRequest, ui: WsClient) -> None:

    try:
        obj_type = glob.OBJECT_TYPES[req.args.id]
    except KeyError:
        raise Arcor2Exception("Unknown object type.")

    if obj_type.meta.built_in:
        raise Arcor2Exception("Can't delete built-in type.")

    for obj in glob.OBJECT_TYPES.values():
        if obj.meta.base == req.args.id:
            raise Arcor2Exception(f"Object type is base of '{obj.meta.type}'.")

    async for scene in scenes():
        check_scene_for_object_type(scene, req.args.id)

    if glob.SCENE:
        check_scene_for_object_type(glob.SCENE, req.args.id)

    if req.dry_run:
        return

    await storage.delete_object_type(req.args.id)

    # do not care so much if delete_model fails
    if obj_type.meta.object_model:
        try:
            await storage.delete_model(obj_type.meta.object_model.model().id)
        except storage.PersistentStorageException as e:
            glob.logger.error(e.message)

    del glob.OBJECT_TYPES[req.args.id]
    asyncio.ensure_future(notif.broadcast_event(
        events.ChangedObjectTypesEvent(events.EventType.REMOVE, data=[obj_type.meta])))
