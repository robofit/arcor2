#!/usr/bin/env python3
# -*- coding: utf-8 -*-


import asyncio
from typing import List, Dict

from websockets.server import WebSocketServerProtocol as WsClient

from arcor2.source.object_types import new_object_type_source
from arcor2 import object_types_utils as otu, helpers as hlp
from arcor2.data.common import Position, Pose
from arcor2.data.object_type import Model3dType, MeshFocusAction
from arcor2.data import rpc, events
from arcor2 import aio_persistent_storage as storage
from arcor2.object_types import Generic
from arcor2.exceptions import Arcor2Exception
from arcor2.parameter_plugins import TYPE_TO_PLUGIN

from arcor2.server.decorators import scene_needed, no_project
from arcor2.server import objects_services_actions as osa, notifications as notif, globals as glob
from arcor2.server.robot import get_end_effector_pose
from arcor2.server.project import scene_object_pose_updated


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

    if not glob.ROBOT_META[inst.__class__.__name__].features.focus:
        raise Arcor2Exception("Robot/service does not support focusing.")

    obj_type = glob.OBJECT_TYPES[osa.get_obj_type_name(obj_id)]

    if not obj_type.object_model or obj_type.object_model.type != Model3dType.MESH:
        raise Arcor2Exception("Only available for objects with mesh model.")

    assert obj_type.object_model.mesh

    focus_points = obj_type.object_model.mesh.focus_points

    if not focus_points:
        raise Arcor2Exception("focusPoints not defined for the mesh.")

    FOCUS_OBJECT_ROBOT[req.args.object_id] = req.args.robot
    FOCUS_OBJECT[obj_id] = {}
    await glob.logger.info(f'Start of focusing for {obj_id}.')
    return None


@no_project
async def focus_object_cb(req: rpc.objects.FocusObjectRequest, ui: WsClient) -> rpc.objects.FocusObjectResponse:

    obj_id = req.args.object_id
    pt_idx = req.args.point_idx

    if obj_id not in glob.SCENE_OBJECT_INSTANCES:
        raise Arcor2Exception("Unknown object_id.")

    obj_type = glob.OBJECT_TYPES[osa.get_obj_type_name(obj_id)]

    assert obj_type.object_model and obj_type.object_model.mesh

    focus_points = obj_type.object_model.mesh.focus_points

    assert focus_points

    if pt_idx < 0 or pt_idx > len(focus_points)-1:
        raise Arcor2Exception("Index out of range.")

    if obj_id not in FOCUS_OBJECT:
        await glob.logger.info(f'Start of focusing for {obj_id}.')
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

    obj_type = glob.OBJECT_TYPES[osa.get_obj_type_name(obj_id)]

    assert obj_type.object_model and obj_type.object_model.mesh

    focus_points = obj_type.object_model.mesh.focus_points

    assert focus_points

    if len(FOCUS_OBJECT[obj_id]) < len(focus_points):
        raise Arcor2Exception("Not all points were done.")

    robot_id, end_effector = FOCUS_OBJECT_ROBOT[obj_id].as_tuple()
    robot_inst = await osa.get_robot_instance(robot_id)
    assert hasattr(robot_inst, "focus")  # mypy does not deal with hasattr

    assert glob.SCENE

    obj = glob.SCENE.object(obj_id)

    fp: List[Position] = []
    rp: List[Position] = []

    for idx, pose in FOCUS_OBJECT[obj_id].items():

        fp.append(focus_points[idx].position)
        rp.append(pose.position)

    mfa = MeshFocusAction(fp, rp)

    await glob.logger.debug(f'Attempt to focus for object {obj_id}, data: {mfa}')

    try:
        obj.pose = await hlp.run_in_executor(robot_inst.focus, mfa)  # type: ignore
    except Arcor2Exception as e:
        await glob.logger.error(f"Focus failed with: {e}, mfa: {mfa}.")
        raise Arcor2Exception("Focusing failed.") from e

    await glob.logger.info(f"Done focusing for {obj_id}.")

    clean_up_after_focus(obj_id)

    asyncio.ensure_future(notif.broadcast_event(events.SceneObjectChanged(events.EventType.UPDATE, data=obj)))
    asyncio.ensure_future(scene_object_pose_updated(glob.SCENE.id, obj.id))
    return None


async def new_object_type_cb(req: rpc.objects.NewObjectTypeRequest, ui: WsClient) -> None:

    meta = req.args

    if meta.type in glob.OBJECT_TYPES:
        raise Arcor2Exception("Object type already exists.")

    if meta.base not in glob.OBJECT_TYPES:
        raise Arcor2Exception(f"Unknown base object type '{meta.base}', "
                              f"known types are: {', '.join(glob.OBJECT_TYPES.keys())}.")

    if not hlp.is_valid_type(meta.type):
        raise Arcor2Exception("Object type invalid (should be CamelCase).")

    if req.dry_run:
        return None

    obj = meta.to_object_type()
    obj.source = new_object_type_source(glob.OBJECT_TYPES[meta.base], meta)

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
            await glob.logger.error(e)
            raise Arcor2Exception(f"Mesh ID {meta.object_model.mesh.id} does not exist.")

    await storage.update_object_type(obj)

    glob.OBJECT_TYPES[meta.type] = meta
    glob.ACTIONS[meta.type] = otu.object_actions(TYPE_TO_PLUGIN,
                                                 hlp.type_def_from_source(obj.source, obj.id, Generic), obj.source)
    otu.add_ancestor_actions(meta.type, glob.ACTIONS, glob.OBJECT_TYPES)

    asyncio.ensure_future(notif.broadcast_event(events.ObjectTypesChangedEvent(data=[meta.type])))
    return None


async def get_object_actions_cb(req: rpc.objects.GetActionsRequest, ui: WsClient) -> rpc.objects.GetActionsResponse:

    try:
        return rpc.objects.GetActionsResponse(data=glob.ACTIONS[req.args.type])
    except KeyError:
        raise Arcor2Exception(f"Unknown object type: '{req.args.type}'.")


async def get_object_types_cb(req: rpc.objects.GetObjectTypesRequest, ui: WsClient) ->\
        rpc.objects.GetObjectTypesResponse:
    return rpc.objects.GetObjectTypesResponse(data=list(glob.OBJECT_TYPES.values()))
