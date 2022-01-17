import asyncio
from dataclasses import dataclass, field
from typing import NamedTuple

from websockets.server import WebSocketServerProtocol as WsClient

from arcor2 import helpers as hlp
from arcor2.cached import CachedProject, CachedScene
from arcor2.clients import aio_scene_service as scene_srv
from arcor2.data import events, rpc
from arcor2.data.common import Parameter, Pose, Position, SceneObject
from arcor2.data.object_type import Model3dType
from arcor2.data.scene import MeshFocusAction
from arcor2.exceptions import Arcor2Exception
from arcor2.object_types.abstract import CollisionObject, GenericWithPose, Robot
from arcor2.source.utils import tree_to_str
from arcor2_arserver import globals as glob
from arcor2_arserver import logger
from arcor2_arserver import notifications as notif
from arcor2_arserver import settings
from arcor2_arserver.clients import project_service as storage
from arcor2_arserver.helpers import ctx_write_lock, ensure_write_locked
from arcor2_arserver.object_types.data import ObjectTypeData
from arcor2_arserver.object_types.source import new_object_type
from arcor2_arserver.object_types.utils import add_ancestor_actions, object_actions, remove_object_type
from arcor2_arserver.objects_actions import update_object_model
from arcor2_arserver.robot import check_eef_arm, get_end_effector_pose
from arcor2_arserver.scene import (
    can_modify_scene,
    ensure_scene_started,
    get_instance,
    get_robot_instance,
    scenes,
    update_scene_object_pose,
)
from arcor2_arserver_data import events as sevts
from arcor2_arserver_data import rpc as srpc


@dataclass
class AimedObject:

    obj_id: str
    robot: rpc.common.RobotArg
    poses: dict[int, Pose] = field(default_factory=dict)


_objects_being_aimed: dict[str, AimedObject] = {}  # key == user_name


async def object_aiming_start_cb(req: srpc.o.ObjectAimingStart.Request, ui: WsClient) -> None:
    """Starts the aiming process for a selected object (with mesh) and robot.

    Only possible when the scene is started/online.
    UI have to acquire write locks for object and robot in advance.
    :param req:
    :param ui:
    :return:
    """

    scene = glob.LOCK.scene_or_exception()

    if glob.LOCK.project:
        raise Arcor2Exception("Project has to be closed first.")

    ensure_scene_started()

    user_name = glob.USERS.user_name(ui)

    if user_name in _objects_being_aimed:
        raise Arcor2Exception("Aiming already started.")

    obj_id = req.args.object_id
    scene_obj = scene.object(obj_id)

    obj_type = glob.OBJECT_TYPES[scene_obj.type].meta

    if not obj_type.has_pose:
        raise Arcor2Exception("Only available for objects with pose.")

    if not obj_type.object_model or obj_type.object_model.type != Model3dType.MESH:
        raise Arcor2Exception("Only available for objects with mesh model.")

    assert obj_type.object_model.mesh

    focus_points = obj_type.object_model.mesh.focus_points

    if not focus_points:
        raise Arcor2Exception("focusPoints not defined for the mesh.")

    await ensure_write_locked(req.args.object_id, user_name)
    await ensure_write_locked(req.args.robot.robot_id, user_name)

    await check_eef_arm(get_robot_instance(req.args.robot.robot_id), req.args.robot.arm_id, req.args.robot.end_effector)

    if req.dry_run:
        return

    _objects_being_aimed[user_name] = AimedObject(req.args.object_id, req.args.robot)
    logger.info(
        f"{user_name} just started aiming of {scene_obj.name} using {scene.object(req.args.robot.robot_id).name}."
    )


class AimingTuple(NamedTuple):
    obj: AimedObject
    user_name: str


async def object_aiming_prune() -> None:
    """Deletes records for users that already lost their locks.

    :return:
    """

    to_delete: list[str] = []

    # users in db but not holding a lock for the object should be deleted
    for un, fo in _objects_being_aimed.items():

        if not await glob.LOCK.is_write_locked(fo.obj_id, un):
            logger.info(f"Object aiming cancelled for {un}.")
            to_delete.append(un)

    for td in to_delete:
        _objects_being_aimed.pop(td, None)


async def object_aiming_check(ui: WsClient) -> AimingTuple:
    """Gets object that is being aimed by the user or exception.

    :param ui:
    :return:
    """

    user_name = glob.USERS.user_name(ui)

    try:
        fo = _objects_being_aimed[user_name]
    except KeyError:
        raise Arcor2Exception("Aiming has to be started first.")

    await ensure_write_locked(fo.obj_id, user_name)
    await ensure_write_locked(fo.robot.robot_id, user_name)

    return AimingTuple(fo, user_name)


async def object_aiming_cancel_cb(req: srpc.o.ObjectAimingCancel.Request, ui: WsClient) -> None:
    """Cancel aiming of the object.

    :param req:
    :param ui:
    :return:
    """

    fo, user_name = await object_aiming_check(ui)

    if req.dry_run:
        return

    _objects_being_aimed.pop(user_name, None)
    if glob.LOCK.scene:
        logger.info(f"Aiming for {glob.LOCK.scene.object(fo.obj_id).name} cancelled by {user_name}.")


async def object_aiming_add_point_cb(
    req: srpc.o.ObjectAimingAddPoint.Request, ui: WsClient
) -> srpc.o.ObjectAimingAddPoint.Response:

    scene = glob.LOCK.scene_or_exception()
    fo, user_name = await object_aiming_check(ui)

    pt_idx = req.args.point_idx
    scene_obj = scene.object(fo.obj_id)
    obj_type = glob.OBJECT_TYPES[scene_obj.type].meta

    assert obj_type.has_pose
    assert obj_type.object_model
    assert obj_type.object_model.mesh

    focus_points = obj_type.object_model.mesh.focus_points

    assert focus_points

    if pt_idx < 0 or pt_idx > len(focus_points) - 1:
        raise Arcor2Exception("Index out of range.")

    robot_id, end_effector, arm_id = fo.robot.as_tuple()

    robot_inst = get_robot_instance(robot_id)

    r = srpc.o.ObjectAimingAddPoint.Response()
    r.data = r.Data(finished_indexes=list(fo.poses.keys()))

    if not req.dry_run:
        fo.poses[pt_idx] = await get_end_effector_pose(robot_inst, end_effector, arm_id)
        r.data = r.Data(finished_indexes=list(fo.poses.keys()))
        logger.info(
            f"{user_name} just aimed index {pt_idx} for {scene_obj.name}. Done indexes: {r.data.finished_indexes}."
        )

    return r


async def object_aiming_done_cb(req: srpc.o.ObjectAimingDone.Request, ui: WsClient) -> None:
    """Calls scene service to get a new pose for the object.

    In case of success, robot and object are kept locked, unlocking is responsibility of ui.
    On failure, UI may do another attempt or call ObjectAimingCancel.

    :param req:
    :param ui:
    :return:
    """

    scene = glob.LOCK.scene_or_exception()
    fo, user_name = await object_aiming_check(ui)

    obj_type = glob.OBJECT_TYPES[scene.object(fo.obj_id).type].meta
    assert obj_type.object_model
    assert obj_type.object_model.mesh

    focus_points = obj_type.object_model.mesh.focus_points

    assert focus_points

    if len(fo.poses) < len(focus_points):
        raise Arcor2Exception(f"Only {len(fo.poses)} points were done out of {len(focus_points)}.")

    obj = scene.object(fo.obj_id)
    assert obj.pose

    obj_inst = get_instance(fo.obj_id, CollisionObject)

    if req.dry_run:
        return

    fp: list[Position] = []
    rp: list[Position] = []

    for idx, pose in fo.poses.items():

        fp.append(focus_points[idx].position)
        rp.append(pose.position)

    mfa = MeshFocusAction(fp, rp)

    logger.debug(f"Attempt to aim object {obj_inst.name}, data: {mfa}")

    try:
        new_pose = await scene_srv.focus(mfa)  # TODO how long does it take?
    except scene_srv.SceneServiceException as e:
        logger.error(f"Aiming failed with: {e}, mfa: {mfa}.")
        raise Arcor2Exception(f"Aiming failed. {str(e)}") from e

    logger.info(f"Done aiming for {obj_inst.name}.")

    _objects_being_aimed.pop(user_name, None)
    asyncio.create_task(update_scene_object_pose(scene, obj, new_pose, obj_inst))
    return None


async def new_object_type_cb(req: srpc.o.NewObjectType.Request, ui: WsClient) -> None:

    async with ctx_write_lock(glob.LOCK.SpecialValues.ADDING_OBJECT, glob.USERS.user_name(ui)):
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

        if issubclass(base.type_def, CollisionObject):
            if not meta.object_model:
                raise Arcor2Exception("Objects based on CollisionObject must have collision model.")
        else:
            if meta.object_model:
                raise Arcor2Exception("Only objects based on CollisionObject can have collision model.")

        if req.dry_run:
            return None

        obj = meta.to_object_type()
        ast = new_object_type(glob.OBJECT_TYPES[meta.base].meta, meta)
        obj.source = tree_to_str(ast)

        if meta.object_model:
            await update_object_model(meta, meta.object_model)

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

        meta.modified = await storage.update_object_type(obj)

        glob.OBJECT_TYPES[meta.type] = ObjectTypeData(meta, type_def, actions, ast)
        add_ancestor_actions(meta.type, glob.OBJECT_TYPES)

        evt = sevts.o.ChangedObjectTypes([meta])
        evt.change_type = events.Event.Type.ADD
        asyncio.ensure_future(notif.broadcast_event(evt))
        return None


async def update_object_model_cb(req: srpc.o.UpdateObjectModel.Request, ui: WsClient) -> None:

    can_modify_scene()
    glob.LOCK.scene_or_exception(True)  # only allow while editing scene

    obj_data = glob.OBJECT_TYPES[req.args.object_type_id]

    if not obj_data.type_def:
        raise Arcor2Exception("ObjectType disabled.")

    if not issubclass(obj_data.type_def, CollisionObject):
        raise Arcor2Exception("Not a CollisionObject.")

    assert obj_data.meta.object_model
    assert obj_data.ast

    if req.args.object_model == obj_data.meta.object_model:
        raise Arcor2Exception("No change requested.")

    await ensure_write_locked(req.args.object_type_id, glob.USERS.user_name(ui))

    if req.dry_run:
        return

    await update_object_model(obj_data.meta, req.args.object_model)
    obj_data.meta.object_model = req.args.object_model

    ot = obj_data.meta.to_object_type()
    ot.source = tree_to_str(obj_data.ast)

    obj_data.meta.modified = await storage.update_object_type(ot)

    evt = sevts.o.ChangedObjectTypes([obj_data.meta])
    evt.change_type = events.Event.Type.UPDATE
    asyncio.ensure_future(notif.broadcast_event(evt))


async def get_object_actions_cb(req: srpc.o.GetActions.Request, ui: WsClient) -> srpc.o.GetActions.Response:
    return srpc.o.GetActions.Response(data=list(glob.OBJECT_TYPES[req.args.type].actions.values()))


async def get_object_types_cb(req: srpc.o.GetObjectTypes.Request, ui: WsClient) -> srpc.o.GetObjectTypes.Response:
    return srpc.o.GetObjectTypes.Response(data=[obj.meta for obj in glob.OBJECT_TYPES.values()])


def check_scene_for_object_type(scene: CachedScene, object_type: str) -> None:

    if object_type in scene.object_types:
        raise Arcor2Exception(f"Used in scene {scene.name}.")


async def delete_object_type_cb(
    req: srpc.o.DeleteObjectTypes.Request, ui: WsClient
) -> srpc.o.DeleteObjectTypes.Response:
    async def _delete_model(obj_type: ObjectTypeData) -> None:

        # do not care so much if delete_model fails
        if not obj_type.meta.object_model:
            return

        try:
            await storage.delete_model(obj_type.meta.object_model.model().id)
        except storage.ProjectServiceException as e:
            logger.error(str(e))

    async def _delete_ot(ot: str) -> None:

        obj_type = glob.OBJECT_TYPES[ot]

        if obj_type.meta.built_in:
            raise Arcor2Exception("Can't delete built-in type.")

        for obj in glob.OBJECT_TYPES.values():
            if obj.meta.base == ot:
                raise Arcor2Exception(f"Object type is base of '{obj.meta.type}'.")

        async for scene in scenes():
            check_scene_for_object_type(scene, ot)

        if glob.LOCK.scene:
            check_scene_for_object_type(glob.LOCK.scene, ot)

        if req.dry_run:
            return

        await asyncio.gather(storage.delete_object_type(ot), _delete_model(obj_type), remove_object_type(ot))

        await glob.LOCK.write_unlock(ot, user_name)  # need to be unlocked while it exists in glob.OBJECT_TYPES
        del glob.OBJECT_TYPES[ot]

        evt = sevts.o.ChangedObjectTypes([obj_type.meta])
        evt.change_type = events.Event.Type.REMOVE
        asyncio.create_task(notif.broadcast_event(evt))

    user_name = glob.USERS.user_name(ui)

    obj_types_to_delete: list[str] = (
        list(req.args)
        if req.args is not None
        else [obj.meta.type for obj in glob.OBJECT_TYPES.values() if not obj.meta.built_in]
    )

    response = srpc.o.DeleteObjectTypes.Response()
    response.data = []

    async with ctx_write_lock(obj_types_to_delete, user_name, auto_unlock=False, dry_run=req.dry_run):

        res = await asyncio.gather(*[_delete_ot(ot) for ot in obj_types_to_delete], return_exceptions=True)

        for idx, r in enumerate(res):
            if isinstance(r, Arcor2Exception):
                response.data.append(srpc.o.DeleteObjectTypes.Response.Data(obj_types_to_delete[idx], str(r)))
            else:
                assert r is None

    if not response.data:
        response.data = None

    if response.data:
        response.result = False
        response.messages = []
        response.messages.append("Failed to delete one or more ObjectTypes.")

    return response


def check_override(
    scene: CachedScene, project: CachedProject, obj_id: str, override: Parameter, add_new_one: bool = False
) -> SceneObject:

    obj = scene.object(obj_id)

    for par in glob.OBJECT_TYPES[obj.type].meta.settings:
        if par.name == override.name:
            if par.type != override.type:
                raise Arcor2Exception("Override can't change parameter type.")
            break
    else:
        raise Arcor2Exception("Unknown parameter name.")

    if add_new_one:
        try:
            for existing_override in project.overrides[obj.id]:
                if override.name == existing_override.name:
                    raise Arcor2Exception("Override already exists.")
        except KeyError:
            pass
    else:
        if obj.id not in project.overrides:
            raise Arcor2Exception("There are no overrides for the object.")

        for override in project.overrides[obj.id]:
            if override.name == override.name:
                break
        else:
            raise Arcor2Exception("Override not found.")

    return obj


async def add_override_cb(req: srpc.o.AddOverride.Request, ui: WsClient) -> None:

    scene = glob.LOCK.scene_or_exception()
    project = glob.LOCK.project_or_exception()

    obj = check_override(scene, project, req.args.id, req.args.override, add_new_one=True)

    await ensure_write_locked(req.args.id, glob.USERS.user_name(ui))

    if req.dry_run:
        return

    if obj.id not in project.overrides:
        project.overrides[obj.id] = []

    project.overrides[obj.id].append(req.args.override)
    project.update_modified()

    evt = sevts.o.OverrideUpdated(req.args.override)
    evt.change_type = events.Event.Type.ADD
    evt.parent_id = req.args.id
    asyncio.ensure_future(notif.broadcast_event(evt))


async def update_override_cb(req: srpc.o.UpdateOverride.Request, ui: WsClient) -> None:

    scene = glob.LOCK.scene_or_exception()
    project = glob.LOCK.project_or_exception()

    obj = check_override(scene, project, req.args.id, req.args.override)

    await ensure_write_locked(req.args.id, glob.USERS.user_name(ui))

    if req.dry_run:
        return

    for override in project.overrides[obj.id]:
        if override.name == override.name:
            override.value = req.args.override.value
    project.update_modified()

    evt = sevts.o.OverrideUpdated(req.args.override)
    evt.change_type = events.Event.Type.UPDATE
    evt.parent_id = req.args.id
    asyncio.ensure_future(notif.broadcast_event(evt))


async def delete_override_cb(req: srpc.o.DeleteOverride.Request, ui: WsClient) -> None:

    scene = glob.LOCK.scene_or_exception()
    project = glob.LOCK.project_or_exception()

    obj = check_override(scene, project, req.args.id, req.args.override)

    await ensure_write_locked(req.args.id, glob.USERS.user_name(ui))

    if req.dry_run:
        return

    project.overrides[obj.id] = [ov for ov in project.overrides[obj.id] if ov.name != req.args.override.name]

    if not project.overrides[obj.id]:
        del project.overrides[obj.id]

    project.update_modified()

    evt = sevts.o.OverrideUpdated(req.args.override)
    evt.change_type = events.Event.Type.REMOVE
    evt.parent_id = req.args.id
    asyncio.ensure_future(notif.broadcast_event(evt))


async def object_type_usage_cb(req: srpc.o.ObjectTypeUsage.Request, ui: WsClient) -> srpc.o.ObjectTypeUsage.Response:

    resp = srpc.o.ObjectTypeUsage.Response()
    resp.data = set()  # mypy does not recognize it correctly with Response(data=set())

    async for scene in scenes():
        if req.args.id in scene.object_types:
            resp.data.add(scene.id)

    return resp
