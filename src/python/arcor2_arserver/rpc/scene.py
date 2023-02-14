import asyncio
import copy
import functools
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import quaternion
from websockets.server import WebSocketServerProtocol as WsClient

from arcor2 import helpers as hlp
from arcor2.cached import UpdateableCachedScene
from arcor2.data import common, object_type
from arcor2.data.events import Event, PackageState
from arcor2.exceptions import Arcor2Exception
from arcor2.image import image_from_str
from arcor2.object_types.abstract import Generic, VirtualCollisionObject
from arcor2.source.utils import tree_to_str
from arcor2_arserver import globals as glob
from arcor2_arserver import logger
from arcor2_arserver import notifications as notif
from arcor2_arserver import settings
from arcor2_arserver.checks import check_object_parameters
from arcor2_arserver.clients import project_service as storage
from arcor2_arserver.common import (
    associated_projects,
    project_names,
    projects_using_object,
    remove_object_references_from_projects,
)
from arcor2_arserver.helpers import (
    ctx_read_lock,
    ctx_write_lock,
    ensure_write_locked,
    get_unlocked_objects,
    unique_name,
)
from arcor2_arserver.lock.exceptions import LockingException
from arcor2_arserver.object_types.data import ObjectTypeData
from arcor2_arserver.object_types.source import new_object_type
from arcor2_arserver.object_types.utils import add_ancestor_actions, object_actions
from arcor2_arserver.objects_actions import get_object_types, update_object_model
from arcor2_arserver.robot import check_eef_arm, get_end_effector_pose
from arcor2_arserver.scene import (
    add_object_to_scene,
    can_modify_scene,
    clear_auto_remove_schedule,
    delete_if_not_used,
    ensure_scene_started,
    get_instance,
    get_robot_instance,
    get_scene_problems,
    get_scene_state,
    notify_scene_closed,
    notify_scene_opened,
    open_scene,
    save_scene,
    scene_names,
    scene_started,
    scenes,
    schedule_auto_remove,
    start_scene,
    stop_scene,
    unschedule_auto_remove,
    update_scene_object_pose,
)
from arcor2_arserver_data import events as sevts
from arcor2_arserver_data import rpc as srpc
from arcor2_arserver_data.objects import ObjectTypeMeta
from arcor2_calibration_data import client as calibration


@asynccontextmanager
async def managed_scene(scene_id: str, make_copy: bool = False) -> AsyncGenerator[UpdateableCachedScene, None]:

    save_back = False

    if glob.LOCK.scene and glob.LOCK.scene.id == scene_id:
        if make_copy:
            scene = copy.deepcopy(glob.LOCK.scene)
            save_back = True
        else:
            scene = glob.LOCK.scene
    else:
        save_back = True
        scene = UpdateableCachedScene(await storage.get_scene(scene_id))

    if make_copy:
        scene.id = common.Scene.uid()

    try:
        yield scene
    finally:
        if save_back:
            asyncio.ensure_future(storage.update_scene(scene))


async def new_scene_cb(req: srpc.s.NewScene.Request, ui: WsClient) -> None:
    """Creates and opens a new scene on the server. Fails if any scene is open
    or if scene id/name already exists.

    :param req:
    :return:
    """

    async with glob.LOCK.get_lock(dry_run=req.dry_run):
        if glob.PACKAGE_STATE.state in PackageState.RUN_STATES:
            raise Arcor2Exception("Can't create scene while package runs.")

        if glob.LOCK.scene:
            raise Arcor2Exception("Scene has to be closed first.")

        unique_name(req.args.name, (await scene_names()))

        # TODO workaround for https://gitlab.com/kinalisoft/test-it-off/project/-/issues/16
        unique_name(req.args.name, (await project_names()))

        if req.dry_run:
            return None

        # TODO get_object_types - not ideal, may take quite long time
        #  ...maybe creating a scene should be done similarly to starting one (process with events about its state)?
        await get_object_types()

        glob.LOCK.scene = UpdateableCachedScene(common.Scene(req.args.name, description=req.args.description))
        asyncio.ensure_future(notify_scene_opened(sevts.s.OpenScene(sevts.s.OpenScene.Data(glob.LOCK.scene.scene))))

        return None


async def close_scene_cb(req: srpc.s.CloseScene.Request, ui: WsClient) -> None:
    """Closes scene on the server.

    :param req:
    :return:
    """

    async with ctx_write_lock(glob.LOCK.SpecialValues.SCENE, glob.USERS.user_name(ui), dry_run=req.dry_run):

        scene = glob.LOCK.scene_or_exception()

        if glob.LOCK.project:
            raise Arcor2Exception("Project has to be closed first.")

        if not req.args.force and scene.has_changes:
            raise Arcor2Exception("Scene has unsaved changes.")

        can_modify_scene()  # can't close scene while started

        if await glob.LOCK.get_locked_roots_count() > 1:
            raise LockingException(glob.LOCK.ErrMessages.SOMETHING_LOCKED.value)

        if req.dry_run:
            return None

        scene_id = scene.id
        glob.LOCK.scene = None
        glob.OBJECTS_WITH_UPDATED_POSE.clear()
        await clear_auto_remove_schedule()
        asyncio.ensure_future(notify_scene_closed(scene_id))


async def save_scene_cb(req: srpc.s.SaveScene.Request, ui: WsClient) -> None:

    async with glob.LOCK.get_lock(req.dry_run):

        scene = glob.LOCK.scene_or_exception()

        if glob.LOCK.project:
            raise Arcor2Exception("Project has to be closed first.")

        if req.dry_run:
            return None

        await save_scene(scene)
        return None


async def open_scene_cb(req: srpc.s.OpenScene.Request, ui: WsClient) -> None:

    async with glob.LOCK.get_lock():
        if glob.PACKAGE_STATE.state in PackageState.RUN_STATES:
            raise Arcor2Exception("Can't open scene while package runs.")

        if glob.LOCK.scene:
            raise Arcor2Exception("Scene already opened.")

        await open_scene(req.args.id)

        assert glob.LOCK.scene
        assert not glob.LOCK.scene.has_changes
        asyncio.ensure_future(
            notify_scene_opened(sevts.s.OpenScene(data=sevts.s.OpenScene.Data(glob.LOCK.scene.scene)))
        )
        return None


async def list_scenes_cb(req: srpc.s.ListScenes.Request, ui: WsClient) -> srpc.s.ListScenes.Response:

    resp = srpc.s.ListScenes.Response()
    resp.data = []

    async for scene in scenes():
        assert scene.created
        assert scene.modified
        resp.data.append(
            resp.Data(
                scene.id, scene.name, scene.created, scene.modified, scene.description, await get_scene_problems(scene)
            )
        )

    return resp


async def get_scene_cb(req: srpc.s.GetScene.Request, ui: WsClient) -> srpc.s.GetScene.Response:

    return srpc.s.GetScene.Response(data=(await storage.get_scene(req.args.id)).scene)


async def add_object_to_scene_cb(req: srpc.s.AddObjectToScene.Request, ui: WsClient) -> None:

    async with ctx_write_lock(glob.LOCK.SpecialValues.SCENE, glob.USERS.user_name(ui)):

        scene = glob.LOCK.scene_or_exception()

        if glob.LOCK.project:
            raise Arcor2Exception("Project has to be closed first.")

        can_modify_scene()

        obj = common.SceneObject(req.args.name, req.args.type, req.args.pose, req.args.parameters)

        await add_object_to_scene(scene, obj, dry_run=req.dry_run)

        if req.dry_run:
            return None

        scene.update_modified()

        asyncio.create_task(unschedule_auto_remove(obj.type))  # TODO could this even be case?

        evt = sevts.s.SceneObjectChanged(obj)
        evt.change_type = Event.Type.ADD
        asyncio.ensure_future(notif.broadcast_event(evt))
        return None


async def update_object_parameters_cb(req: srpc.s.UpdateObjectParameters.Request, ui: WsClient) -> None:

    scene = glob.LOCK.scene_or_exception(ensure_project_closed=True)

    can_modify_scene()

    obj = scene.object(req.args.id)

    if obj.type not in glob.OBJECT_TYPES:
        raise Arcor2Exception("Unknown object type.")

    obj_type = glob.OBJECT_TYPES[obj.type]

    check_object_parameters(obj_type, req.args.parameters)

    await ensure_write_locked(req.args.id, glob.USERS.user_name(ui))

    if req.dry_run:
        return None

    obj.parameters = req.args.parameters
    scene.update_modified()

    evt = sevts.s.SceneObjectChanged(obj)
    evt.change_type = Event.Type.UPDATE
    asyncio.ensure_future(notif.broadcast_event(evt))
    return None


async def scene_object_usage_request_cb(
    req: srpc.s.SceneObjectUsage.Request, ui: WsClient
) -> srpc.s.SceneObjectUsage.Response:
    """Works for both services and objects.

    :param req:
    :return:
    """

    scene = glob.LOCK.scene_or_exception()

    async with ctx_read_lock(req.args.id, glob.USERS.user_name(ui)):
        if not (any(obj.id == req.args.id for obj in scene.objects)):
            raise Arcor2Exception("Unknown ID.")

        resp = srpc.s.SceneObjectUsage.Response()
        resp.data = set()

        async for project in projects_using_object(scene.id, req.args.id):
            resp.data.add(project.id)

        return resp


# TODO move to objects
async def action_param_values_cb(
    req: srpc.o.ActionParamValues.Request, ui: WsClient
) -> srpc.o.ActionParamValues.Response:

    glob.LOCK.scene_or_exception()

    async with ctx_read_lock(req.args.id, glob.USERS.user_name(ui)):
        ensure_scene_started()

        inst = get_instance(req.args.id, Generic)

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

        resp = srpc.o.ActionParamValues.Response()

        try:
            method = getattr(inst, method_name)
        except AttributeError:
            logger.error(
                f"Unable to get values for parameter {req.args.param_id}, "
                f"object/service {inst.id} has no method named {method_name}."
            )
            raise Arcor2Exception("System error.")

        # TODO update hlp.run_in_executor to support kwargs
        resp.data = await asyncio.get_event_loop().run_in_executor(None, functools.partial(method, **parent_params))
        return resp


async def remove_from_scene_cb(req: srpc.s.RemoveFromScene.Request, ui: WsClient) -> None:

    scene = glob.LOCK.scene_or_exception(ensure_project_closed=True)
    user_name = glob.USERS.user_name(ui)

    to_lock = await get_unlocked_objects(req.args.id, user_name)
    async with ctx_write_lock(to_lock, user_name, auto_unlock=req.dry_run):

        can_modify_scene()

        if not req.args.force and {proj.name async for proj in projects_using_object(scene.id, req.args.id)}:
            raise Arcor2Exception("Can't remove object that is used in project(s).")

        if req.dry_run:
            return None

        if req.args.id not in scene.object_ids:
            raise Arcor2Exception("Unknown id.")

        await glob.LOCK.write_unlock(req.args.id, user_name)

        obj = scene.object(req.args.id)
        scene.delete_object(req.args.id)

        if req.args.id in glob.OBJECTS_WITH_UPDATED_POSE:
            glob.OBJECTS_WITH_UPDATED_POSE.remove(req.args.id)

        evt = sevts.s.SceneObjectChanged(obj)
        evt.change_type = Event.Type.REMOVE
        asyncio.ensure_future(notif.broadcast_event(evt))

        # TODO this should be done after scene is saved
        asyncio.ensure_future(remove_object_references_from_projects(req.args.id))

        if (meta := glob.OBJECT_TYPES[obj.type].meta).base == VirtualCollisionObject.__name__:
            await schedule_auto_remove(meta.type)


async def update_object_pose_using_robot_cb(req: srpc.o.UpdateObjectPoseUsingRobot.Request, ui: WsClient) -> None:
    """Updates object's pose using a pose of the robot's end effector.

    :param req:
    :return:
    """

    if req.args.id == req.args.robot.robot_id:
        raise Arcor2Exception("Robot cannot update its own pose.")

    scene = glob.LOCK.scene_or_exception(ensure_project_closed=True)
    user_name = glob.USERS.user_name(ui)

    to_lock = await get_unlocked_objects([obj for obj in (req.args.robot.robot_id, req.args.id)], user_name)
    async with ctx_write_lock(to_lock, user_name):
        ensure_scene_started()

        robot_inst = get_robot_instance(req.args.robot.robot_id)
        await check_eef_arm(robot_inst, req.args.robot.arm_id, req.args.robot.end_effector)

        scene_object = scene.object(req.args.id)

        obj_type = glob.OBJECT_TYPES[scene_object.type]

        if not obj_type.meta.has_pose:
            raise Arcor2Exception("Object without pose.")

        object_model = obj_type.meta.object_model

        if object_model:
            collision_model = object_model.model()
            if isinstance(collision_model, object_type.Mesh) and req.args.pivot != req.args.PivotEnum.MIDDLE:
                raise Arcor2Exception("Only middle pivot point is supported for objects with mesh collision model.")
        elif req.args.pivot != req.args.PivotEnum.MIDDLE:
            raise Arcor2Exception("Only middle pivot point is supported for objects without collision model.")

        new_pose = await get_end_effector_pose(robot_inst, req.args.robot.end_effector, req.args.robot.arm_id)

        position_delta = common.Position()

        if object_model:
            collision_model = object_model.model()
            if isinstance(collision_model, object_type.Box):
                if req.args.pivot == req.args.PivotEnum.TOP:
                    position_delta.z -= collision_model.size_z / 2
                elif req.args.pivot == req.args.PivotEnum.BOTTOM:
                    position_delta.z += collision_model.size_z / 2
            elif isinstance(collision_model, object_type.Cylinder):
                if req.args.pivot == req.args.PivotEnum.TOP:
                    position_delta.z -= collision_model.height / 2
                elif req.args.pivot == req.args.PivotEnum.BOTTOM:
                    position_delta.z += collision_model.height / 2
            elif isinstance(collision_model, object_type.Sphere):
                if req.args.pivot == req.args.PivotEnum.TOP:
                    position_delta.z -= collision_model.radius / 2
                elif req.args.pivot == req.args.PivotEnum.BOTTOM:
                    position_delta.z += collision_model.radius / 2

        position_delta = position_delta.rotated(new_pose.orientation)

        assert scene_object.pose

        scene_object.pose.position = new_pose.position - position_delta

        scene_object.pose.orientation.set_from_quaternion(
            new_pose.orientation.as_quaternion() * quaternion.quaternion(0, 1, 0, 0)
        )

        asyncio.ensure_future(update_scene_object_pose(scene, scene_object))
        return None


async def update_object_pose_cb(req: srpc.s.UpdateObjectPose.Request, ui: WsClient) -> None:

    scene = glob.LOCK.scene_or_exception(ensure_project_closed=True)

    if scene_started():
        try:
            get_robot_instance(req.args.object_id)
        except Arcor2Exception:
            pass  # ok, it should not be a robot
        else:
            raise Arcor2Exception("Robot's pose can be only updated offline.")

    obj = scene.object(req.args.object_id)

    if not obj.pose:
        raise Arcor2Exception("Object without pose.")

    await ensure_write_locked(req.args.object_id, glob.USERS.user_name(ui))

    if req.dry_run:
        return

    asyncio.ensure_future(update_scene_object_pose(scene, obj, req.args.pose))
    return None


async def rename_object_cb(req: srpc.s.RenameObject.Request, ui: WsClient) -> None:

    scene = glob.LOCK.scene_or_exception(ensure_project_closed=True)
    target_obj = scene.object(req.args.id)

    if target_obj.name == req.args.new_name:
        raise Arcor2Exception("Name unchanged")

    for obj_name in scene.object_names():
        if obj_name == req.args.new_name:
            raise Arcor2Exception("Object name already exists.")

    hlp.is_valid_identifier(req.args.new_name)

    user_name = glob.USERS.user_name(ui)
    await ensure_write_locked(req.args.id, user_name)

    if req.dry_run:
        return None

    target_obj.name = req.args.new_name

    scene.update_modified()

    evt = sevts.s.SceneObjectChanged(target_obj)
    evt.change_type = Event.Type.UPDATE
    asyncio.ensure_future(notif.broadcast_event(evt))

    await glob.LOCK.write_unlock(req.args.id, user_name, True)
    return None


async def rename_scene_cb(req: srpc.s.RenameScene.Request, ui: WsClient) -> None:

    unique_name(req.args.new_name, (await scene_names()))

    # TODO workaround for https://gitlab.com/kinalisoft/test-it-off/project/-/issues/16
    unique_name(req.args.new_name, (await project_names()))

    user_name = glob.USERS.user_name(ui)
    await ensure_write_locked(req.args.id, user_name)

    if req.dry_run:
        return None

    async with managed_scene(req.args.id) as scene:
        scene.name = req.args.new_name

        evt = sevts.s.SceneChanged(scene.bare)
        evt.change_type = Event.Type.UPDATE_BASE
        asyncio.ensure_future(notif.broadcast_event(evt))

    await glob.LOCK.write_unlock(req.args.id, user_name, True)
    return None


async def delete_scene_cb(req: srpc.s.DeleteScene.Request, ui: WsClient) -> None | srpc.s.DeleteScene.Response:

    if glob.LOCK.scene:
        raise Arcor2Exception("Scene has to be closed first.")

    user_name = glob.USERS.user_name(ui)

    async with ctx_write_lock(req.args.id, user_name, auto_unlock=req.dry_run):

        if assoc_projects := await associated_projects(req.args.id):
            resp = srpc.s.DeleteScene.Response(result=False)
            resp.messages = ["Scene has associated projects."]
            resp.data = assoc_projects
            await glob.LOCK.write_unlock(req.args.id, user_name)
            return resp

        if req.dry_run:
            return None

        scene = UpdateableCachedScene(await storage.get_scene(req.args.id))
        await glob.LOCK.write_unlock(req.args.id, user_name)
        await storage.delete_scene(req.args.id)

        for obj_type in scene.object_types:
            if (meta := glob.OBJECT_TYPES[obj_type].meta).base == VirtualCollisionObject.__name__:
                logger.debug(f"VCO {meta.type} will be (probably) auto-removed.")
                asyncio.create_task(delete_if_not_used(meta))

        evt = sevts.s.SceneChanged(scene.bare)
        evt.change_type = Event.Type.REMOVE
        asyncio.ensure_future(notif.broadcast_event(evt))
        return None


async def projects_with_scene_cb(
    req: srpc.s.ProjectsWithScene.Request, ui: WsClient
) -> srpc.s.ProjectsWithScene.Response:

    async with ctx_read_lock(req.args.id, glob.USERS.user_name(ui)):
        resp = srpc.s.ProjectsWithScene.Response()
        resp.data = await associated_projects(req.args.id)
        return resp


async def update_scene_description_cb(req: srpc.s.UpdateSceneDescription.Request, ui: WsClient) -> None:

    async with ctx_write_lock(req.args.scene_id, glob.USERS.user_name(ui)):
        async with managed_scene(req.args.scene_id) as scene:
            scene.description = req.args.new_description
            scene.update_modified()

            evt = sevts.s.SceneChanged(scene.bare)
            evt.change_type = Event.Type.UPDATE_BASE
            asyncio.ensure_future(notif.broadcast_event(evt))
        return None


async def copy_scene_cb(req: srpc.s.CopyScene.Request, ui: WsClient) -> None:

    async with ctx_write_lock(req.args.source_id, glob.USERS.user_name(ui)):
        # TODO check if target_name is unique
        async with managed_scene(req.args.source_id, make_copy=True) as scene:
            scene.name = req.args.target_name

            evt = sevts.s.SceneChanged(scene.bare)
            evt.change_type = Event.Type.UPDATE_BASE
            asyncio.ensure_future(notif.broadcast_event(evt))

        return None


# TODO maybe this would better fit into another category of RPCs? Like common/misc?
async def get_camera_pose_cb(req: srpc.c.GetCameraPose.Request, ui: WsClient) -> srpc.c.GetCameraPose.Response:

    try:
        return srpc.c.GetCameraPose.Response(
            data=await hlp.run_in_executor(
                calibration.estimate_camera_pose,
                req.args.camera_parameters,
                image_from_str(req.args.image),
                req.args.inverse,
            )
        )
    except calibration.MarkerNotFound:  # this is ok
        raise
    except calibration.CalibrationException as e:  # this means a serious problem and should be logged
        logger.warn(f"Failed to get camera pose. {str(e)}")
        raise


# TODO maybe this would better fit into another category of RPCs? Like common/misc?
async def marker_corners_cb(req: srpc.c.MarkersCorners.Request, ui: WsClient) -> srpc.c.MarkersCorners.Response:

    return srpc.c.MarkersCorners.Response(
        data=await hlp.run_in_executor(
            calibration.markers_corners, req.args.camera_parameters, image_from_str(req.args.image)
        )
    )


async def start_scene_cb(req: srpc.s.StartScene.Request, ui: WsClient) -> None:

    scene = glob.LOCK.scene_or_exception()

    if get_scene_state().data.state != sevts.s.SceneState.Data.StateEnum.Stopped:
        raise Arcor2Exception("Scene not stopped.")

    # online scene can't be modified so we demand that UIs free all their locks first
    # when editing project, changes can be done both online and offline
    if not glob.LOCK.project and await glob.LOCK.get_write_locks_count():
        raise LockingException(glob.LOCK.ErrMessages.SOMETHING_LOCKED.value)

    if await glob.LOCK.is_write_locked(glob.LOCK.SpecialValues.SCENE, glob.LOCK.Owners.SERVER):
        raise Arcor2Exception("Scene locked.")

    if await glob.LOCK.is_write_locked(glob.LOCK.SpecialValues.PROJECT, glob.LOCK.Owners.SERVER):
        raise Arcor2Exception("Project locked.")

    if req.dry_run:
        return

    asyncio.ensure_future(start_scene(scene))


async def stop_scene_cb(req: srpc.s.StopScene.Request, ui: WsClient) -> None:

    scene = glob.LOCK.scene_or_exception()

    if get_scene_state().data.state != sevts.s.SceneState.Data.StateEnum.Started:
        raise Arcor2Exception("Scene not started.")

    if await glob.LOCK.is_write_locked(glob.LOCK.SpecialValues.SCENE, glob.LOCK.Owners.SERVER):
        raise Arcor2Exception("Scene locked.")

    if await glob.LOCK.is_write_locked(glob.LOCK.SpecialValues.PROJECT, glob.LOCK.Owners.SERVER):
        raise Arcor2Exception("Project locked.")

    if glob.RUNNING_ACTION:  # TODO acquire lock?
        raise Arcor2Exception("There is a running action.")

    if req.dry_run:
        return

    asyncio.ensure_future(stop_scene(scene))


async def add_virtual_collision_object_to_scene_cb(
    req: srpc.s.AddVirtualCollisionObjectToScene.Request, ui: WsClient
) -> None:

    async with ctx_write_lock(
        (glob.LOCK.SpecialValues.SCENE, glob.LOCK.SpecialValues.ADDING_OBJECT), glob.USERS.user_name(ui)
    ):

        scene = glob.LOCK.scene_or_exception()

        if glob.LOCK.project:
            raise Arcor2Exception("Project has to be closed first.")

        can_modify_scene()

        if req.args.name in glob.OBJECT_TYPES:
            raise Arcor2Exception("ObjectType already exists.")

        if req.args.name in scene.object_names():
            raise Arcor2Exception("Name has to be unique.")

        hlp.is_valid_identifier(req.args.name)

        # post_init of ObjectTypeMeta check if ObjectType.id == model.id
        meta = ObjectTypeMeta(
            req.args.name, base=VirtualCollisionObject.__name__, object_model=req.args.model, has_pose=True
        )

        if req.dry_run:
            return None

        ast = new_object_type(glob.OBJECT_TYPES[VirtualCollisionObject.__name__].meta, meta)
        source = tree_to_str(ast)

        assert meta.object_model
        await update_object_model(meta, meta.object_model)

        type_def = await hlp.run_in_executor(
            hlp.save_and_import_type_def,
            source,
            req.args.name,
            VirtualCollisionObject,
            settings.OBJECT_TYPE_PATH,
            settings.OBJECT_TYPE_MODULE,
        )
        assert issubclass(type_def, VirtualCollisionObject)
        actions = object_actions(type_def, ast)

        meta.modified = await storage.update_object_type(meta.to_object_type(source))

        glob.OBJECT_TYPES[meta.type] = ObjectTypeData(meta, type_def, actions, ast)
        add_ancestor_actions(meta.type, glob.OBJECT_TYPES)

        evt = sevts.o.ChangedObjectTypes([meta])
        evt.change_type = Event.Type.ADD
        asyncio.ensure_future(notif.broadcast_event(evt))

        obj = common.SceneObject(req.args.name, req.args.name, req.args.pose)
        scene.upsert_object(obj)  # add_object_to_scene(scene, obj) would do some unnecessary checks

        evt2 = sevts.s.SceneObjectChanged(obj)
        evt2.change_type = Event.Type.ADD
        asyncio.ensure_future(notif.broadcast_event(evt2))

        # for a case when user created VCO of the type which already existed before (and was deleted)
        asyncio.create_task(unschedule_auto_remove(obj.type))

        return None
