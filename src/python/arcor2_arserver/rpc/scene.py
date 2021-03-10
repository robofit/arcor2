import asyncio
import copy
import functools
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional

import quaternion
from arcor2_calibration_data import client as calibration
from websockets.server import WebSocketServerProtocol as WsClient

from arcor2 import helpers as hlp
from arcor2.cached import UpdateableCachedScene
from arcor2.clients import aio_scene_service as scene_srv
from arcor2.data import common, object_type
from arcor2.data.events import Event, PackageState
from arcor2.exceptions import Arcor2Exception
from arcor2.image import image_from_str
from arcor2_arserver import globals as glob
from arcor2_arserver import notifications as notif
from arcor2_arserver.clients import persistent_storage as storage
from arcor2_arserver.decorators import no_project, no_scene, scene_needed
from arcor2_arserver.helpers import unique_name
from arcor2_arserver.objects_actions import get_object_types
from arcor2_arserver.project import (
    associated_projects,
    invalidate_joints_using_object_as_parent,
    projects_using_object,
    remove_object_references_from_projects,
)
from arcor2_arserver.robot import get_end_effector_pose
from arcor2_arserver.scene import (
    add_object_to_scene,
    can_modify_scene,
    check_object_parameters,
    ensure_scene_started,
    get_instance,
    get_scene_state,
    notify_scene_closed,
    open_scene,
    scene_names,
    scenes,
    start_scene,
    stop_scene,
    update_scene_object_pose,
)
from arcor2_arserver_data import events as sevts
from arcor2_arserver_data import rpc as srpc


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
        scene.id = common.Scene.uid()

    try:
        yield scene
    finally:
        if save_back:
            asyncio.ensure_future(storage.update_scene(scene.scene))


@no_scene
async def new_scene_cb(req: srpc.s.NewScene.Request, ui: WsClient) -> None:
    """Creates and opens a new scene on the server. Fails if any scene is open
    or if scene id/name already exists.

    :param req:
    :return:
    """

    if glob.PACKAGE_STATE.state in PackageState.RUN_STATES:
        raise Arcor2Exception("Can't create scene while package runs.")

    assert glob.SCENE is None

    for scene_id in (await storage.get_scenes()).items:
        if req.args.name == scene_id.name:
            raise Arcor2Exception("Name already used.")

    if req.dry_run:
        return None

    await get_object_types()  # TODO not ideal, may take quite long time
    glob.SCENE = UpdateableCachedScene(common.Scene(req.args.name, desc=req.args.desc))
    asyncio.ensure_future(notif.broadcast_event(sevts.s.OpenScene(sevts.s.OpenScene.Data(glob.SCENE.scene))))
    asyncio.ensure_future(scene_srv.delete_all_collisions())  # just for sure
    return None


@scene_needed
@no_project
async def close_scene_cb(req: srpc.s.CloseScene.Request, ui: WsClient) -> None:
    """Closes scene on the server.

    :param req:
    :return:
    """

    assert glob.SCENE

    if not req.args.force and glob.SCENE.has_changes():
        raise Arcor2Exception("Scene has unsaved changes.")

    can_modify_scene()  # can't close scene while started

    if req.dry_run:
        return None

    scene_id = glob.SCENE.id
    glob.SCENE = None
    glob.OBJECTS_WITH_UPDATED_POSE.clear()
    asyncio.ensure_future(notify_scene_closed(scene_id))


@scene_needed
@no_project
async def save_scene_cb(req: srpc.s.SaveScene.Request, ui: WsClient) -> None:

    assert glob.SCENE
    glob.SCENE.modified = await storage.update_scene(glob.SCENE.scene)
    asyncio.ensure_future(notif.broadcast_event(sevts.s.SceneSaved()))
    for obj_id in glob.OBJECTS_WITH_UPDATED_POSE:
        asyncio.ensure_future(invalidate_joints_using_object_as_parent(glob.SCENE.object(obj_id)))
    glob.OBJECTS_WITH_UPDATED_POSE.clear()
    return None


@no_project
async def open_scene_cb(req: srpc.s.OpenScene.Request, ui: WsClient) -> None:

    if glob.PACKAGE_STATE.state in PackageState.RUN_STATES:
        raise Arcor2Exception("Can't open scene while package runs.")

    await open_scene(req.args.id)
    assert glob.SCENE
    assert glob.SCENE.int_modified is None
    assert not glob.SCENE.has_changes()
    asyncio.ensure_future(notif.broadcast_event(sevts.s.OpenScene(data=sevts.s.OpenScene.Data(glob.SCENE.scene))))
    return None


async def list_scenes_cb(req: srpc.s.ListScenes.Request, ui: WsClient) -> srpc.s.ListScenes.Response:

    resp = srpc.s.ListScenes.Response()
    resp.data = []

    async for scene in scenes():
        resp.data.append(resp.Data(scene.id, scene.name, scene.desc, scene.modified))

    return resp


@scene_needed
@no_project
async def add_object_to_scene_cb(req: srpc.s.AddObjectToScene.Request, ui: WsClient) -> None:

    assert glob.SCENE

    can_modify_scene()

    obj = common.SceneObject(req.args.name, req.args.type, req.args.pose, req.args.parameters)

    await add_object_to_scene(obj, dry_run=req.dry_run)

    if req.dry_run:
        return None

    glob.SCENE.update_modified()

    evt = sevts.s.SceneObjectChanged(obj)
    evt.change_type = Event.Type.ADD
    asyncio.ensure_future(notif.broadcast_event(evt))
    return None


@scene_needed
@no_project
async def update_object_parameters_cb(req: srpc.s.UpdateObjectParameters.Request, ui: WsClient) -> None:

    assert glob.SCENE

    can_modify_scene()

    obj = glob.SCENE.object(req.args.id)

    if obj.type not in glob.OBJECT_TYPES:
        raise Arcor2Exception("Unknown object type.")

    obj_type = glob.OBJECT_TYPES[obj.type]

    check_object_parameters(obj_type, req.args.parameters)

    if req.dry_run:
        return None

    obj.parameters = req.args.parameters
    glob.SCENE.update_modified()

    evt = sevts.s.SceneObjectChanged(obj)
    evt.change_type = Event.Type.UPDATE
    asyncio.ensure_future(notif.broadcast_event(evt))
    return None


@scene_needed
async def scene_object_usage_request_cb(
    req: srpc.s.SceneObjectUsage.Request, ui: WsClient
) -> srpc.s.SceneObjectUsage.Response:
    """Works for both services and objects.

    :param req:
    :return:
    """

    assert glob.SCENE

    if not (any(obj.id == req.args.id for obj in glob.SCENE.objects)):
        raise Arcor2Exception("Unknown ID.")

    resp = srpc.s.SceneObjectUsage.Response()
    resp.data = set()

    async for project in projects_using_object(glob.SCENE.id, req.args.id):
        resp.data.add(project.id)

    return resp


# TODO move to objects
@scene_needed
async def action_param_values_cb(
    req: srpc.o.ActionParamValues.Request, ui: WsClient
) -> srpc.o.ActionParamValues.Response:

    ensure_scene_started()

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

    resp = srpc.o.ActionParamValues.Response()

    try:
        method = getattr(inst, method_name)
    except AttributeError:
        glob.logger.error(
            f"Unable to get values for parameter {req.args.param_id}, "
            f"object/service {inst.id} has no method named {method_name}."
        )
        raise Arcor2Exception("System error.")

    # TODO update hlp.run_in_executor to support kwargs
    resp.data = await asyncio.get_event_loop().run_in_executor(None, functools.partial(method, **parent_params))
    return resp


@scene_needed
@no_project
async def remove_from_scene_cb(req: srpc.s.RemoveFromScene.Request, ui: WsClient) -> None:

    assert glob.SCENE

    can_modify_scene()

    if not req.args.force and {proj.name async for proj in projects_using_object(glob.SCENE.id, req.args.id)}:
        raise Arcor2Exception("Can't remove object that is used in project(s).")

    if req.dry_run:
        return None

    if req.args.id not in glob.SCENE.object_ids:
        raise Arcor2Exception("Unknown id.")

    obj = glob.SCENE.object(req.args.id)
    glob.SCENE.delete_object(req.args.id)

    if req.args.id in glob.OBJECTS_WITH_UPDATED_POSE:
        glob.OBJECTS_WITH_UPDATED_POSE.remove(req.args.id)

    evt = sevts.s.SceneObjectChanged(obj)
    evt.change_type = Event.Type.REMOVE
    asyncio.ensure_future(notif.broadcast_event(evt))

    # TODO this should be done after scene is saved
    asyncio.ensure_future(remove_object_references_from_projects(req.args.id))
    return None


@scene_needed
@no_project
async def update_object_pose_using_robot_cb(req: srpc.o.UpdateObjectPoseUsingRobot.Request, ui: WsClient) -> None:
    """Updates object's pose using a pose of the robot's end effector.

    :param req:
    :return:
    """

    assert glob.SCENE

    ensure_scene_started()

    if req.args.id == req.args.robot.robot_id:
        raise Arcor2Exception("Robot cannot update its own pose.")

    scene_object = glob.SCENE.object(req.args.id)

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

    new_pose = await get_end_effector_pose(req.args.robot.robot_id, req.args.robot.end_effector)

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

    scene_object.pose.position.x = new_pose.position.x - position_delta.x
    scene_object.pose.position.y = new_pose.position.y - position_delta.y
    scene_object.pose.position.z = new_pose.position.z - position_delta.z

    scene_object.pose.orientation.set_from_quaternion(
        new_pose.orientation.as_quaternion() * quaternion.quaternion(0, 1, 0, 0)
    )

    asyncio.ensure_future(update_scene_object_pose(scene_object))
    return None


@scene_needed
@no_project
async def update_object_pose_cb(req: srpc.s.UpdateObjectPose.Request, ui: WsClient) -> None:

    can_modify_scene()

    assert glob.SCENE

    obj = glob.SCENE.object(req.args.object_id)

    if not obj.pose:
        raise Arcor2Exception("Object without pose.")

    if req.dry_run:
        return

    asyncio.ensure_future(update_scene_object_pose(obj, req.args.pose))
    return None


@scene_needed
@no_project
async def rename_object_cb(req: srpc.s.RenameObject.Request, ui: WsClient) -> None:

    assert glob.SCENE

    target_obj = glob.SCENE.object(req.args.id)

    if target_obj.name == req.args.new_name:
        return

    for obj_name in glob.SCENE.object_names():
        if obj_name == req.args.new_name:
            raise Arcor2Exception("Object name already exists.")

    hlp.is_valid_identifier(req.args.new_name)

    if req.dry_run:
        return None

    target_obj.name = req.args.new_name

    glob.SCENE.update_modified()

    evt = sevts.s.SceneObjectChanged(target_obj)
    evt.change_type = Event.Type.UPDATE
    asyncio.ensure_future(notif.broadcast_event(evt))
    return None


async def rename_scene_cb(req: srpc.s.RenameScene.Request, ui: WsClient) -> None:

    unique_name(req.args.new_name, (await scene_names()))

    if req.dry_run:
        return None

    async with managed_scene(req.args.id) as scene:
        scene.name = req.args.new_name

        evt = sevts.s.SceneChanged(scene.bare)
        evt.change_type = Event.Type.UPDATE_BASE
        asyncio.ensure_future(notif.broadcast_event(evt))
    return None


@no_scene
async def delete_scene_cb(req: srpc.s.DeleteScene.Request, ui: WsClient) -> Optional[srpc.s.DeleteScene.Response]:

    assoc_projects = await associated_projects(req.args.id)

    if assoc_projects:
        resp = srpc.s.DeleteScene.Response(result=False)
        resp.messages = ["Scene has associated projects."]
        resp.data = assoc_projects
        return resp

    if req.dry_run:
        return None

    scene = UpdateableCachedScene(await storage.get_scene(req.args.id))
    await storage.delete_scene(req.args.id)
    evt = sevts.s.SceneChanged(scene.bare)
    evt.change_type = Event.Type.REMOVE
    asyncio.ensure_future(notif.broadcast_event(evt))
    return None


async def projects_with_scene_cb(
    req: srpc.s.ProjectsWithScene.Request, ui: WsClient
) -> srpc.s.ProjectsWithScene.Response:

    resp = srpc.s.ProjectsWithScene.Response()
    resp.data = await associated_projects(req.args.id)
    return resp


async def update_scene_description_cb(req: srpc.s.UpdateSceneDescription.Request, ui: WsClient) -> None:

    async with managed_scene(req.args.scene_id) as scene:
        scene.desc = req.args.new_description
        scene.update_modified()

        evt = sevts.s.SceneChanged(scene.bare)
        evt.change_type = Event.Type.UPDATE_BASE
        asyncio.ensure_future(notif.broadcast_event(evt))
    return None


async def copy_scene_cb(req: srpc.s.CopyScene.Request, ui: WsClient) -> None:

    # TODO check if target_name is unique
    async with managed_scene(req.args.source_id, make_copy=True) as scene:
        scene.name = req.args.target_name

        evt = sevts.s.SceneChanged(scene.bare)
        evt.change_type = Event.Type.UPDATE_BASE
        asyncio.ensure_future(notif.broadcast_event(evt))

    return None


# TODO maybe this would better fit into another category of RPCs? Like common/misc?
async def calibration_cb(req: srpc.c.GetCameraPose.Request, ui: WsClient) -> srpc.c.GetCameraPose.Response:

    # TODO estimated pose should be rather returned in an event (it is possibly a long-running process)
    return srpc.c.GetCameraPose.Response(
        data=await hlp.run_in_executor(
            calibration.estimate_camera_pose, req.args.camera_parameters, image_from_str(req.args.image)
        )
    )


# TODO maybe this would better fit into another category of RPCs? Like common/misc?
async def marker_corners_cb(req: srpc.c.MarkersCorners.Request, ui: WsClient) -> srpc.c.MarkersCorners.Response:

    # TODO should be rather returned in an event (it is possibly a long-running process)
    return srpc.c.MarkersCorners.Response(
        data=await hlp.run_in_executor(
            calibration.markers_corners, req.args.camera_parameters, image_from_str(req.args.image)
        )
    )


async def start_scene_cb(req: srpc.s.StartScene.Request, ui: WsClient) -> None:

    if get_scene_state() != sevts.s.SceneState.Data.StateEnum.Stopped:
        raise Arcor2Exception("Scene not stopped.")

    if req.dry_run:
        return

    asyncio.ensure_future(start_scene())


async def stop_scene_cb(req: srpc.s.StopScene.Request, ui: WsClient) -> None:

    # TODO it should not be possible to stop scene while some action runs

    if get_scene_state() != sevts.s.SceneState.Data.StateEnum.Started:
        raise Arcor2Exception("Scene not started.")

    if req.dry_run:
        return

    asyncio.ensure_future(stop_scene())
