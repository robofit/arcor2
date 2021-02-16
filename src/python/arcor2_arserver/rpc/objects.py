import asyncio
from typing import Dict, List

from websockets.server import WebSocketServerProtocol as WsClient

from arcor2 import helpers as hlp
from arcor2.cached import CachedScene
from arcor2.clients import aio_scene_service as scene_srv
from arcor2.data import events, rpc
from arcor2.data.common import Parameter, Pose, Position, SceneObject
from arcor2.data.object_type import Model3dType
from arcor2.data.scene import MeshFocusAction
from arcor2.exceptions import Arcor2Exception
from arcor2.object_types.abstract import GenericWithPose, Robot
from arcor2.source.utils import tree_to_str
from arcor2_arserver import globals as glob
from arcor2_arserver import notifications as notif
from arcor2_arserver import objects_actions as osa
from arcor2_arserver import settings
from arcor2_arserver.clients import persistent_storage as storage
from arcor2_arserver.decorators import no_project, project_needed, scene_needed
from arcor2_arserver.object_types.data import ObjectTypeData
from arcor2_arserver.object_types.source import new_object_type
from arcor2_arserver.object_types.utils import add_ancestor_actions, object_actions, remove_object_type
from arcor2_arserver.robot import get_end_effector_pose
from arcor2_arserver.scene import ensure_scene_started, scenes, update_scene_object_pose
from arcor2_arserver_data import events as sevts
from arcor2_arserver_data import rpc as srpc

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
async def focus_object_start_cb(req: srpc.o.FocusObjectStart.Request, ui: WsClient) -> None:

    ensure_scene_started()

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
    glob.logger.info(f"Start of focusing for {obj_id}.")
    return None


@no_project
async def focus_object_cb(req: srpc.o.FocusObject.Request, ui: WsClient) -> srpc.o.FocusObject.Response:

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
        glob.logger.info(f"Start of focusing for {obj_id}.")
        FOCUS_OBJECT[obj_id] = {}

    robot_id, end_effector = FOCUS_OBJECT_ROBOT[obj_id].as_tuple()

    FOCUS_OBJECT[obj_id][pt_idx] = await get_end_effector_pose(robot_id, end_effector)

    r = srpc.o.FocusObject.Response()
    r.data = r.Data(finished_indexes=list(FOCUS_OBJECT[obj_id].keys()))
    return r


@scene_needed
@no_project
async def focus_object_done_cb(req: srpc.o.FocusObjectDone.Request, ui: WsClient) -> None:

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

    glob.logger.debug(f"Attempt to focus for object {obj_id}, data: {mfa}")

    try:
        new_pose = await scene_srv.focus(mfa)
    except scene_srv.SceneServiceException as e:
        glob.logger.error(f"Focus failed with: {e}, mfa: {mfa}.")
        raise Arcor2Exception("Focusing failed.") from e

    glob.logger.info(f"Done focusing for {obj_id}.")

    clean_up_after_focus(obj_id)

    asyncio.ensure_future(update_scene_object_pose(obj, new_pose, obj_inst))

    return None


async def new_object_type_cb(req: srpc.o.NewObjectType.Request, ui: WsClient) -> None:

    meta = req.args

    if meta.type in glob.OBJECT_TYPES:
        raise Arcor2Exception("Object type already exists.")

    hlp.is_valid_type(meta.type)

    if meta.base not in glob.OBJECT_TYPES:
        raise Arcor2Exception(
            f"Unknown base object type '{meta.base}', " f"known types are: {', '.join(glob.OBJECT_TYPES.keys())}."
        )

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

    if meta.object_model:

        if meta.object_model.type == Model3dType.MESH:

            # TODO check whether mesh id exists - if so, then use existing mesh, if not, upload a new one
            # ...get whole mesh (focus_points) based on mesh id
            assert meta.object_model.mesh
            try:
                meta.object_model.mesh = await storage.get_mesh(meta.object_model.mesh.id)
            except storage.ProjectServiceException as e:
                glob.logger.error(e)
                raise Arcor2Exception(f"Mesh ID {meta.object_model.mesh.id} does not exist.")

        else:

            meta.object_model.model().id = meta.type
            await storage.put_model(meta.object_model.model())

    type_def = await hlp.run_in_executor(
        hlp.save_and_import_type_def,
        obj.source,
        obj.id,
        base.type_def,
        settings.OBJECT_TYPE_PATH,
        settings.OBJECT_TYPE_MODULE,
    )
    assert issubclass(type_def, base.type_def)
    actions = object_actions(type_def, ast)

    await storage.update_object_type(obj)

    glob.OBJECT_TYPES[meta.type] = ObjectTypeData(meta, type_def, actions, ast)
    add_ancestor_actions(meta.type, glob.OBJECT_TYPES)

    evt = sevts.o.ChangedObjectTypes([meta])
    evt.change_type = events.Event.Type.ADD
    asyncio.ensure_future(notif.broadcast_event(evt))
    return None


async def get_object_actions_cb(req: srpc.o.GetActions.Request, ui: WsClient) -> srpc.o.GetActions.Response:

    try:
        return srpc.o.GetActions.Response(data=list(glob.OBJECT_TYPES[req.args.type].actions.values()))
    except KeyError:
        raise Arcor2Exception(f"Unknown object type: '{req.args.type}'.")


async def get_object_types_cb(req: srpc.o.GetObjectTypes.Request, ui: WsClient) -> srpc.o.GetObjectTypes.Response:
    return srpc.o.GetObjectTypes.Response(data=[obj.meta for obj in glob.OBJECT_TYPES.values()])


def check_scene_for_object_type(scene: CachedScene, object_type: str) -> None:

    if list(scene.objects_of_type(object_type)):
        raise Arcor2Exception(f"Object type used in scene '{scene.name}'.")


async def delete_object_type_cb(req: srpc.o.DeleteObjectType.Request, ui: WsClient) -> None:

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
        except storage.ProjectServiceException as e:
            glob.logger.error(str(e))

    del glob.OBJECT_TYPES[req.args.id]
    remove_object_type(req.args.id)

    evt = sevts.o.ChangedObjectTypes([obj_type.meta])
    evt.change_type = events.Event.Type.REMOVE
    asyncio.ensure_future(notif.broadcast_event(evt))


def check_override(obj_id: str, override: Parameter, add_new_one: bool = False) -> SceneObject:

    assert glob.SCENE
    assert glob.PROJECT

    obj = glob.SCENE.object(obj_id)

    for par in glob.OBJECT_TYPES[obj.type].meta.settings:
        if par.name == override.name:
            if par.type != override.type:
                raise Arcor2Exception("Override can't change parameter type.")
            break
    else:
        raise Arcor2Exception("Unknown parameter name.")

    if add_new_one:
        try:
            for existing_override in glob.PROJECT.overrides[obj.id]:
                if override.name == existing_override.name:
                    raise Arcor2Exception("Override already exists.")
        except KeyError:
            pass
    else:
        if obj.id not in glob.PROJECT.overrides:
            raise Arcor2Exception("There are no overrides for the object.")

        for override in glob.PROJECT.overrides[obj.id]:
            if override.name == override.name:
                break
        else:
            raise Arcor2Exception("Override not found.")

    return obj


@project_needed
async def add_override_cb(req: srpc.o.AddOverride.Request, ui: WsClient) -> None:

    assert glob.PROJECT

    obj = check_override(req.args.id, req.args.override, add_new_one=True)

    if req.dry_run:
        return

    if obj.id not in glob.PROJECT.overrides:
        glob.PROJECT.overrides[obj.id] = []

    glob.PROJECT.overrides[obj.id].append(req.args.override)
    glob.PROJECT.update_modified()

    evt = sevts.o.OverrideUpdated(req.args.override)
    evt.change_type = events.Event.Type.ADD
    evt.parent_id = req.args.id
    asyncio.ensure_future(notif.broadcast_event(evt))


@project_needed
async def update_override_cb(req: srpc.o.UpdateOverride.Request, ui: WsClient) -> None:

    assert glob.PROJECT

    obj = check_override(req.args.id, req.args.override)

    if req.dry_run:
        return

    for override in glob.PROJECT.overrides[obj.id]:
        if override.name == override.name:
            override.value = req.args.override.value
    glob.PROJECT.update_modified()

    evt = sevts.o.OverrideUpdated(req.args.override)
    evt.change_type = events.Event.Type.UPDATE
    evt.parent_id = req.args.id
    asyncio.ensure_future(notif.broadcast_event(evt))


@project_needed
async def delete_override_cb(req: srpc.o.DeleteOverride.Request, ui: WsClient) -> None:

    assert glob.PROJECT

    obj = check_override(req.args.id, req.args.override)

    if req.dry_run:
        return

    glob.PROJECT.overrides[obj.id] = [ov for ov in glob.PROJECT.overrides[obj.id] if ov.name != req.args.override.name]

    if not glob.PROJECT.overrides[obj.id]:
        del glob.PROJECT.overrides[obj.id]

    glob.PROJECT.update_modified()

    evt = sevts.o.OverrideUpdated(req.args.override)
    evt.change_type = events.Event.Type.REMOVE
    evt.parent_id = req.args.id
    asyncio.ensure_future(notif.broadcast_event(evt))
