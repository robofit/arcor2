#!/usr/bin/env python3
# -*- coding: utf-8 -*-


import asyncio
from typing import Union, List, Dict

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
async def focus_object_start_cb(req: rpc.objects.FocusObjectStartRequest) -> Union[rpc.objects.FocusObjectStartResponse,
                                                                                   hlp.RPC_RETURN_TYPES]:

    obj_id = req.args.object_id

    if obj_id in FOCUS_OBJECT_ROBOT:
        return False, "Focusing already started."

    if obj_id not in glob.SCENE_OBJECT_INSTANCES:
        return False, "Unknown object."

    try:
        inst = await osa.get_robot_instance(req.args.robot.robot_id, req.args.robot.end_effector)
    except Arcor2Exception as e:
        return False, e.message

    if not glob.ROBOT_META[inst.__class__.__name__].features.focus:
        return False, "Robot/service does not support focusing."

    obj_type = glob.OBJECT_TYPES[osa.get_obj_type_name(obj_id)]

    if not obj_type.object_model or obj_type.object_model.type != Model3dType.MESH:
        return False, "Only available for objects with mesh model."

    assert obj_type.object_model.mesh

    focus_points = obj_type.object_model.mesh.focus_points

    if not focus_points:
        return False, "focusPoints not defined for the mesh."

    FOCUS_OBJECT_ROBOT[req.args.object_id] = req.args.robot
    FOCUS_OBJECT[obj_id] = {}
    await glob.logger.info(f'Start of focusing for {obj_id}.')
    return None


@no_project
async def focus_object_cb(req: rpc.objects.FocusObjectRequest) -> Union[rpc.objects.FocusObjectResponse,
                                                                        hlp.RPC_RETURN_TYPES]:

    obj_id = req.args.object_id
    pt_idx = req.args.point_idx

    if obj_id not in glob.SCENE_OBJECT_INSTANCES:
        return False, "Unknown object_id."

    obj_type = glob.OBJECT_TYPES[osa.get_obj_type_name(obj_id)]

    assert obj_type.object_model and obj_type.object_model.mesh

    focus_points = obj_type.object_model.mesh.focus_points

    assert focus_points

    if pt_idx < 0 or pt_idx > len(focus_points)-1:
        return False, "Index out of range."

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
async def focus_object_done_cb(req: rpc.objects.FocusObjectDoneRequest) -> Union[rpc.objects.FocusObjectDoneResponse,
                                                                                 hlp.RPC_RETURN_TYPES]:

    obj_id = req.args.id

    if obj_id not in FOCUS_OBJECT:
        return False, "focusObjectStart/focusObject has to be called first."

    obj_type = glob.OBJECT_TYPES[osa.get_obj_type_name(obj_id)]

    assert obj_type.object_model and obj_type.object_model.mesh

    focus_points = obj_type.object_model.mesh.focus_points

    assert focus_points

    if len(FOCUS_OBJECT[obj_id]) < len(focus_points):
        return False, "Not all points were done."

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
        return False, "Focusing failed."

    await glob.logger.info(f"Done focusing for {obj_id}.")

    clean_up_after_focus(obj_id)

    asyncio.ensure_future(notif.broadcast_event(events.SceneObjectChanged(events.EventType.UPDATE, data=obj)))
    asyncio.ensure_future(scene_object_pose_updated(glob.SCENE.id, obj.id))
    return None


async def new_object_type_cb(req: rpc.objects.NewObjectTypeRequest) -> Union[rpc.objects.NewObjectTypeResponse,
                                                                             hlp.RPC_RETURN_TYPES]:

    meta = req.args

    if meta.type in glob.OBJECT_TYPES:
        return False, "Object type already exists."

    if meta.base not in glob.OBJECT_TYPES:
        return False, f"Unknown base object type '{meta.base}', known types are: {', '.join(glob.OBJECT_TYPES.keys())}."

    if not hlp.is_valid_type(meta.type):
        return False, "Object type invalid (should be CamelCase)."

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
            return False, f"Mesh ID {meta.object_model.mesh.id} does not exist."

    await storage.update_object_type(obj)

    glob.OBJECT_TYPES[meta.type] = meta
    glob.ACTIONS[meta.type] = otu.object_actions(TYPE_TO_PLUGIN,
                                                 hlp.type_def_from_source(obj.source, obj.id, Generic), obj.source)
    otu.add_ancestor_actions(meta.type, glob.ACTIONS, glob.OBJECT_TYPES)

    asyncio.ensure_future(notif.broadcast_event(events.ObjectTypesChangedEvent(data=[meta.type])))
    return None


async def get_object_actions_cb(req: rpc.objects.GetActionsRequest) -> Union[rpc.objects.GetActionsResponse,
                                                                             hlp.RPC_RETURN_TYPES]:

    try:
        return rpc.objects.GetActionsResponse(data=glob.ACTIONS[req.args.type])
    except KeyError:
        return False, f"Unknown object type: '{req.args.type}'."


async def get_object_types_cb(req: rpc.objects.GetObjectTypesRequest) -> rpc.objects.GetObjectTypesResponse:
    return rpc.objects.GetObjectTypesResponse(data=list(glob.OBJECT_TYPES.values()))
