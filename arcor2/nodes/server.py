#!/usr/bin/env python3
# -*- coding: utf-8 -*-


import asyncio
import base64
import json
import functools
import sys
from typing import Dict, Set, Union, TYPE_CHECKING, Tuple, Optional, List, Callable, cast, AsyncIterator, \
    get_type_hints, Type, Any
import uuid
import argparse
import os
import tempfile

import websockets
from websockets.server import WebSocketServerProtocol
from aiologger import Logger  # type: ignore
from aiologger.levels import LogLevel  # type: ignore

import arcor2
from arcor2.source.logic import program_src
from arcor2.source.object_types import new_object_type_source
from arcor2.source import SourceException
from arcor2 import nodes
from arcor2 import service_types_utils as stu, object_types_utils as otu, helpers as hlp
from arcor2.data.common import Scene, Project, Pose, Position, SceneObject, SceneService, ActionIOEnum,\
    Joint, NamedOrientation, RobotJoints
from arcor2.data.object_type import ObjectActionsDict, ObjectTypeMetaDict, ModelTypeEnum, \
    MeshFocusAction, ObjectModel, Models
from arcor2.data.services import ServiceTypeMeta
from arcor2.data.robot import RobotMeta
from arcor2.data import rpc
from arcor2.data.events import ProjectChangedEvent, SceneChangedEvent, Event, ObjectTypesChangedEvent, \
    ProjectStateEvent, ActionStateEvent, CurrentActionEvent
from arcor2.data.helpers import RPC_MAPPING
from arcor2.persistent_storage import PersistentStorageException
from arcor2 import aio_persistent_storage as storage
from arcor2.object_types import Generic, Robot
from arcor2.project_utils import get_object_ap
from arcor2.scene_utils import get_scene_object
from arcor2.exceptions import ActionPointNotFound, SceneObjectNotFound, Arcor2Exception
from arcor2.services import Service, RobotService
from arcor2.parameter_plugins import TYPE_TO_PLUGIN, PARAM_PLUGINS
from arcor2.parameter_plugins.base import TypesDict, ParameterPluginException
from arcor2 import action as action_mod
from arcor2 import rest

# disables before/after messages, etc.
action_mod.HANDLE_ACTIONS = False


if TYPE_CHECKING:
    ReqQueue = asyncio.Queue[rpc.common.Request]
    RespQueue = asyncio.Queue[rpc.common.Response]
else:
    ReqQueue = asyncio.Queue
    RespQueue = asyncio.Queue


logger = Logger.with_default_handlers(name='server', formatter=hlp.aiologger_formatter(), level=LogLevel.DEBUG)

MANAGER_URL = os.getenv("ARCOR2_EXECUTION_URL", f"ws://0.0.0.0:{nodes.execution.PORT}")
BUILDER_URL = os.getenv("ARCOR2_BUILDER_URL", f"http://0.0.0.0:{nodes.build.PORT}")

SCENE: Union[Scene, None] = None
PROJECT: Union[Project, None] = None

INTERFACES: Set[WebSocketServerProtocol] = set()

MANAGER_RPC_REQUEST_QUEUE: ReqQueue = ReqQueue()
MANAGER_RPC_RESPONSES: Dict[int, RespQueue] = {}

OBJECT_TYPES: ObjectTypeMetaDict = {}
SERVICE_TYPES: Dict[str, ServiceTypeMeta] = {}
ROBOT_META: Dict[str, RobotMeta] = {}
TYPE_DEF_DICT: TypesDict = {}

# TODO merge it into one dict?
SCENE_OBJECT_INSTANCES: Dict[str, Generic] = {}
SERVICES_INSTANCES: Dict[str, Service] = {}

ACTIONS: ObjectActionsDict = {}  # used for actions of both object_types / services

FOCUS_OBJECT: Dict[str, Dict[int, Pose]] = {}  # object_id / idx, pose
FOCUS_OBJECT_ROBOT: Dict[str, rpc.common.RobotArg] = {}  # key: object_id


RUNNING_ACTION: Optional[str] = None


class RobotPoseException(Arcor2Exception):
    pass


# TODO refactor into server_utils
def scene_needed(coro):
    @functools.wraps(coro)
    async def async_wrapper(*args, **kwargs):

        if SCENE is None or not SCENE.id:
            return False, "Scene not opened or has invalid id."
        return await coro(*args, **kwargs)

    return async_wrapper


def no_project(coro):
    @functools.wraps(coro)
    async def async_wrapper(*args, **kwargs):
        if PROJECT:
            return False, "Not available during project editing."
        return await coro(*args, **kwargs)

    return async_wrapper


def project_needed(coro):
    @functools.wraps(coro)
    async def async_wrapper(*args, **kwargs):

        if PROJECT is None or not PROJECT.id:
            return False, "Project not opened or has invalid id."
        return await coro(*args, **kwargs)

    return async_wrapper


async def handle_manager_incoming_messages(manager_client):

    try:

        async for message in manager_client:

            msg = json.loads(message)

            if "event" in msg and INTERFACES:
                await asyncio.wait([intf.send(message) for intf in INTERFACES])
            elif "response" in msg:

                # TODO handle potential errors
                _, resp_cls = RPC_MAPPING[msg["response"]]
                resp = resp_cls.from_dict(msg)
                MANAGER_RPC_RESPONSES[resp.id].put_nowait(resp)

    except websockets.exceptions.ConnectionClosed:
        await logger.error("Connection to manager closed.")


async def project_manager_client() -> None:

    while True:

        await logger.info("Attempting connection to manager...")

        try:

            async with websockets.connect(MANAGER_URL) as manager_client:

                await logger.info("Connected to manager.")

                future = asyncio.ensure_future(handle_manager_incoming_messages(manager_client))

                while True:

                    if future.done():
                        break

                    try:
                        msg = await asyncio.wait_for(MANAGER_RPC_REQUEST_QUEUE.get(), 1.0)
                    except asyncio.TimeoutError:
                        continue

                    try:
                        await manager_client.send(msg.to_json())
                    except websockets.exceptions.ConnectionClosed:
                        await MANAGER_RPC_REQUEST_QUEUE.put(msg)
                        break
        except ConnectionRefusedError as e:
            await logger.error(e)
            await asyncio.sleep(delay=1.0)


def scene_event() -> SceneChangedEvent:

    return SceneChangedEvent(SCENE)


def project_event() -> ProjectChangedEvent:

    return ProjectChangedEvent(PROJECT)


async def notify(event: Event, exclude_ui=None):

    if (exclude_ui is None and INTERFACES) or (exclude_ui and len(INTERFACES) > 1):
        message = event.to_json()
        await asyncio.wait([intf.send(message) for intf in INTERFACES if intf != exclude_ui])


async def _notify(interface, msg_source: Callable[[], Event]):

    await notify(msg_source(), interface)


async def notify_scene_change_to_others(interface: Optional[WebSocketServerProtocol] = None) -> None:

    await _notify(interface, scene_event)


async def notify_project_change_to_others(interface=None) -> None:

    await _notify(interface, project_event)


async def notify_scene(interface) -> None:
    message = scene_event().to_json()
    await asyncio.wait([interface.send(message)])


async def notify_project(interface) -> None:
    message = project_event().to_json()
    await asyncio.wait([interface.send(message)])


async def _initialize_server() -> None:

    while True:  # wait until Project service becomes available
        try:
            await storage.get_projects()
            break
        except storage.PersistentStorageException:
            await asyncio.sleep(1)

    await asyncio.wait([_get_object_types(), _get_service_types()])
    await asyncio.wait([_get_object_actions(), _check_manager()])

    bound_handler = functools.partial(hlp.server, logger=logger, register=register, unregister=unregister,
                                      rpc_dict=RPC_DICT, event_dict=EVENT_DICT)

    await logger.info("Server initialized.")
    await asyncio.wait([websockets.serve(bound_handler, '0.0.0.0', 6789)])


async def _get_robot_meta(robot_type: Union[Type[Robot], Type[RobotService]]) -> None:

    meta = RobotMeta(robot_type.__name__)
    meta.features.focus = hasattr(robot_type, "focus")  # TODO more sophisticated test? (attr(s) and return value?)
    ROBOT_META[robot_type.__name__] = meta


async def _get_service_types() -> None:

    global SERVICE_TYPES

    service_types: Dict[str, ServiceTypeMeta] = {}

    srv_ids = await storage.get_service_type_ids()

    for srv_id in srv_ids.items:

        srv_type = await storage.get_service_type(srv_id.id)
        try:
            type_def = hlp.type_def_from_source(srv_type.source, srv_type.id, Service)
            service_types[srv_id.id] = stu.meta_from_def(type_def)
            TYPE_DEF_DICT[srv_id.id] = type_def
        except Arcor2Exception as e:
            await logger.error(f"Ignoring service type {srv_type.id}: {e}")
            continue

        if issubclass(type_def, RobotService):
            asyncio.ensure_future(_get_robot_meta(type_def))

    SERVICE_TYPES = service_types


async def _get_object_types() -> None:

    global OBJECT_TYPES

    object_types: ObjectTypeMetaDict = otu.built_in_types_meta()

    obj_ids = await storage.get_object_type_ids()

    for obj_id in obj_ids.items:
        obj = await storage.get_object_type(obj_id.id)
        try:
            type_def = hlp.type_def_from_source(obj.source, obj.id, Generic)
            object_types[obj.id] = otu.meta_from_def(type_def)
            TYPE_DEF_DICT[obj.id] = type_def
        except (otu.ObjectTypeException, hlp.TypeDefException) as e:
            await logger.error(f"Ignoring object type {obj.id}: {e}")
            continue

        if obj.model:
            model = await storage.get_model(obj.model.id, obj.model.type)
            kwargs = {model.type().value.lower(): model}
            object_types[obj.id].object_model = ObjectModel(model.type(), **kwargs)  # type: ignore

        if issubclass(type_def, Robot):
            asyncio.ensure_future(_get_robot_meta(type_def))

    # if description is missing, try to get it from ancestor(s), or forget the object type
    to_delete: Set[str] = set()

    for obj_type, obj_meta in object_types.items():
        if not obj_meta.description:
            try:
                obj_meta.description = otu.obj_description_from_base(object_types, obj_meta)
            except otu.DataError as e:
                await logger.error(f"Failed to get info from base for {obj_type}, error: '{e}'.")
                to_delete.add(obj_type)

    for obj_type in to_delete:
        del object_types[obj_type]

    OBJECT_TYPES = object_types


async def get_object_types_cb(req: rpc.objects.GetObjectTypesRequest) -> rpc.objects.GetObjectTypesResponse:
    return rpc.objects.GetObjectTypesResponse(data=list(OBJECT_TYPES.values()))


async def get_services_cb(req: rpc.services.GetServicesRequest) -> rpc.services.GetServicesResponse:
    return rpc.services.GetServicesResponse(data=list(SERVICE_TYPES.values()))


@scene_needed
@no_project
async def save_scene_cb(req: rpc.scene_project.SaveSceneRequest) -> Union[rpc.scene_project.SaveSceneResponse,
                                                                          hlp.RPC_RETURN_TYPES]:

    assert SCENE

    try:
        stored_scene = await storage.get_scene(SCENE.id)
    except storage.PersistentStorageException:
        # new scene, no need for further checks
        await storage.update_scene(SCENE)
        return None

    # let's check if something important has changed
    for old_obj in stored_scene.objects:
        for new_obj in SCENE.objects:
            if old_obj.id != new_obj.id:
                continue

            if old_obj.pose != new_obj.pose:
                asyncio.ensure_future(scene_object_pose_updated(SCENE.id, new_obj.id))

    await storage.update_scene(SCENE)
    return None


@scene_needed
@project_needed
async def save_project_cb(req: rpc.scene_project.SaveProjectRequest) -> Union[rpc.scene_project.SaveProjectResponse,
                                                                              hlp.RPC_RETURN_TYPES]:

    assert SCENE and PROJECT
    await storage.update_project(PROJECT)
    return None


async def open_scene(scene_id: str):

    global SCENE
    SCENE = await storage.get_scene(scene_id)

    for srv in SCENE.services:
        res, msg = await add_service_to_scene(srv)
        if not res:
            await logger.error(msg)

    for obj in SCENE.objects:
        res, msg = await add_object_to_scene(obj, add_to_scene=False, srv_obj_ok=True)
        if not res:
            await logger.error(msg)

    assert {srv.type for srv in SCENE.services} == SERVICES_INSTANCES.keys()
    assert {obj.id for obj in SCENE.objects} == SCENE_OBJECT_INSTANCES.keys()

    asyncio.ensure_future(notify_scene_change_to_others())


async def open_project(project_id: str) -> None:

    global PROJECT

    PROJECT = await storage.get_project(project_id)
    await open_scene(PROJECT.scene_id)

    assert SCENE
    for obj in PROJECT.objects:
        try:
            scene_obj = SCENE.object_or_service(obj.id)
        except Arcor2Exception as e:
            await logger.error(e)
            # TODO remove object from project?
            continue
        obj.uuid = scene_obj.uuid

    asyncio.ensure_future(notify_project_change_to_others())


@no_project
async def open_scene_cb(req: rpc.scene_project.OpenSceneRequest) -> Union[rpc.scene_project.OpenSceneResponse,
                                                                          hlp.RPC_RETURN_TYPES]:

    await open_scene(req.args.id)
    return None


async def open_project_cb(req: rpc.scene_project.OpenProjectRequest) -> Union[rpc.scene_project.OpenProjectResponse,
                                                                              hlp.RPC_RETURN_TYPES]:

    # TODO validate using project_problems?
    await open_project(req.args.id)
    return None


async def _get_object_actions() -> None:  # TODO do it in parallel

    global ACTIONS

    object_actions_dict: ObjectActionsDict = otu.built_in_types_actions(TYPE_TO_PLUGIN)

    for obj_type, obj in OBJECT_TYPES.items():

        if obj.built_in:  # built-in types are already there
            continue

        # db-stored (user-created) object types
        obj_db = await storage.get_object_type(obj_type)
        try:
            type_def = hlp.type_def_from_source(obj_db.source, obj_db.id, Generic)
            object_actions_dict[obj_type] = otu.object_actions(TYPE_TO_PLUGIN, type_def, obj_db.source)
        except hlp.TypeDefException as e:
            await logger.error(e)

    # add actions from ancestors
    for obj_type in OBJECT_TYPES.keys():
        otu.add_ancestor_actions(obj_type, object_actions_dict, OBJECT_TYPES)

    # get services' actions
    for service_type, service_meta in SERVICE_TYPES.items():
        srv_type = await storage.get_service_type(service_type)
        try:
            srv_type_def = hlp.type_def_from_source(srv_type.source, service_type, Service)
            object_actions_dict[service_type] = otu.object_actions(TYPE_TO_PLUGIN, srv_type_def, srv_type.source)
        except (hlp.TypeDefException, otu.ObjectTypeException) as e:
            await logger.warning(e)

    ACTIONS = object_actions_dict

    await notify(ObjectTypesChangedEvent(data=list(object_actions_dict.keys())))


async def _check_manager() -> None:
    """
    Loads project if it is loaded on manager
    :return:
    """

    # TODO avoid cast
    resp = cast(rpc.execution.ProjectStateResponse,
                await manager_request(rpc.execution.ProjectStateRequest(id=uuid.uuid4().int)))  # type: ignore

    if resp.data.id is not None and (PROJECT is None or PROJECT.id != resp.data.id):
        await open_project(resp.data.id)


async def get_object_actions_cb(req: rpc.objects.GetActionsRequest) -> Union[rpc.objects.GetActionsResponse,
                                                                             hlp.RPC_RETURN_TYPES]:

    try:
        return rpc.objects.GetActionsResponse(data=ACTIONS[req.args.type])
    except KeyError:
        return False, f"Unknown object type: '{req.args.type}'."


async def manager_request(req: rpc.common.Request) -> rpc.common.Response:

    assert req.id not in MANAGER_RPC_RESPONSES

    MANAGER_RPC_RESPONSES[req.id] = RespQueue(maxsize=1)
    await MANAGER_RPC_REQUEST_QUEUE.put(req)

    resp = await MANAGER_RPC_RESPONSES[req.id].get()
    del MANAGER_RPC_RESPONSES[req.id]
    return resp


async def get_robot_joints(robot_id: str) -> List[Joint]:
    """
    :param robot_id:
    :return: List of joints
    """

    robot_inst = await get_robot_instance(robot_id)

    if isinstance(robot_inst, Robot):

        try:
            return await hlp.run_in_executor(robot_inst.robot_joints)
        except NotImplementedError:
            raise RobotPoseException("The robot does not support getting joints.")

    elif isinstance(robot_inst, RobotService):

        try:
            return await hlp.run_in_executor(robot_inst.robot_joints, robot_id)
        except NotImplementedError:
            raise RobotPoseException("The robot does not support getting joints.")

    else:
        raise Arcor2Exception("Not a robot instance.")


async def get_end_effector_pose(robot_id: str, end_effector: str) -> Pose:
    """
    :param robot_id:
    :param end_effector:
    :return: Global pose
    """

    robot_inst = await get_robot_instance(robot_id, end_effector)

    if isinstance(robot_inst, Robot):

        try:
            return await hlp.run_in_executor(robot_inst.get_end_effector_pose, end_effector)
        except NotImplementedError:
            raise RobotPoseException("The robot does not support getting pose.")

    elif isinstance(robot_inst, RobotService):

        try:
            return await hlp.run_in_executor(robot_inst.get_end_effector_pose, robot_id, end_effector)
        except NotImplementedError:
            raise RobotPoseException("The robot does not support getting pose.")

    else:
        raise Arcor2Exception("Not a robot instance.")


@scene_needed
@project_needed
async def update_ap_joints_cb(req: rpc.objects.UpdateActionPointJointsRequest) -> \
        Union[rpc.objects.UpdateActionPointJointsResponse, hlp.RPC_RETURN_TYPES]:

    assert SCENE and PROJECT

    try:
        proj_obj, ap = get_object_ap(PROJECT, req.args.id)
    except ActionPointNotFound:
        return False, "Invalid action point."

    try:
        new_joints = await get_robot_joints(req.args.robot_id)
    except Arcor2Exception as e:
        return False, str(e)

    for orientation in ap.orientations:
        if orientation.id == req.args.joints_id:
            return False, "Can't update joints that are paired with orientation."

    for joint in ap.robot_joints:  # update existing joints_id
        if joint.id == req.args.joints_id:
            joint.joints = new_joints
            joint.robot_id = req.args.robot_id
            joint.is_valid = True
            break
    else:
        ap.robot_joints.append(RobotJoints(req.args.joints_id, req.args.robot_id, new_joints))

    asyncio.ensure_future(notify_project_change_to_others())
    return None


@scene_needed
@project_needed
async def update_action_point_cb(req: rpc.objects.UpdateActionPointPoseRequest) -> \
        Union[rpc.objects.UpdateActionPointPoseResponse, hlp.RPC_RETURN_TYPES]:

    assert SCENE and PROJECT

    try:
        proj_obj, ap = get_object_ap(PROJECT, req.args.id)
    except ActionPointNotFound:
        return False, "Invalid action point."

    try:
        new_pose, new_joints = await asyncio.gather(get_end_effector_pose(req.args.robot.robot_id,
                                                                          req.args.robot.end_effector),
                                                    get_robot_joints(req.args.robot.robot_id))
    except RobotPoseException as e:
        return False, str(e)

    rel_pose = hlp.make_pose_rel(SCENE_OBJECT_INSTANCES[proj_obj.id].pose, new_pose)

    if req.args.update_position:
        ap.position = rel_pose.position

    for ori in ap.orientations:
        if ori.id == req.args.orientation_id:
            ori.orientation = rel_pose.orientation
            break
    else:
        ap.orientations.append(NamedOrientation(req.args.orientation_id, rel_pose.orientation))

    for joint in ap.robot_joints:
        if joint.id == req.args.orientation_id:
            joint.joints = new_joints
            joint.robot_id = req.args.robot.robot_id
            joint.is_valid = True
            break
    else:
        ap.robot_joints.append(RobotJoints(req.args.orientation_id, req.args.robot.robot_id, new_joints))

    asyncio.ensure_future(notify_project_change_to_others())
    return None


@scene_needed
@no_project
async def update_action_object_cb(req: rpc.objects.UpdateActionObjectPoseRequest) -> \
        Union[rpc.objects.UpdateActionObjectPoseRequest, hlp.RPC_RETURN_TYPES]:

    assert SCENE

    if req.args.id == req.args.robot.robot_id:
        return False, "Robot cannot update its own pose."

    try:
        scene_object = get_scene_object(SCENE, req.args.id)
    except SceneObjectNotFound:
        return False, "Invalid action object."

    try:
        scene_object.pose = await get_end_effector_pose(req.args.robot.robot_id, req.args.robot.end_effector)
    except RobotPoseException as e:
        return False, str(e)

    asyncio.ensure_future(notify_scene_change_to_others())
    return None


def project_problems(scene: Scene, project: Project) -> List[str]:

    scene_objects: Dict[str, str] = {obj.id: obj.type for obj in scene.objects}
    scene_services: Set[str] = {srv.type for srv in scene.services}

    action_ids: Set[str] = set()
    problems: List[str] = []

    unknown_types = ({obj.type for obj in scene.objects} | scene_services) - ACTIONS.keys()

    if unknown_types:
        return [f"Scene invalid, contains unknown types: {unknown_types}."]

    for obj in project.objects:

        # test if all objects exists in scene
        if obj.id not in scene_objects:
            problems.append(f"Object ID {obj.id} does not exist in scene.")
            continue

        for ap in obj.action_points:

            for joints in ap.robot_joints:
                if not joints.is_valid:
                    problems.append(f"Action point {ap.id} has invalid joints: {joints.id} (robot {joints.robot_id}).")

            for action in ap.actions:

                if action.id in action_ids:
                    problems.append(f"Action ID {action.id} of the {obj.id}/{ap.id} is not unique.")

                # check if objects have used actions
                obj_id, action_type = action.parse_type()

                if obj_id not in scene_objects.keys() | scene_services:
                    problems.append(f"Object ID {obj.id} which action is used in {action.id} does not exist in scene.")
                    continue

                try:
                    os_type = scene_objects[obj_id]  # object type
                except KeyError:
                    os_type = obj_id  # service

                for act in ACTIONS[os_type]:
                    if action_type == act.name:
                        break
                else:
                    problems.append(f"Object type {scene_objects[obj_id]} does not have action {action_type} "
                                    f"used in {action.id}.")

                # check object's actions parameters
                action_params: Dict[str, str] = \
                    {param.id: param.type for param in action.parameters}
                ot_params: Dict[str, str] = {param.name: param.type for param in act.parameters
                                             for act in ACTIONS[os_type]}

                if action_params != ot_params:
                    problems.append(f"Action ID {action.id} of type {action.type} has invalid parameters.")

                # TODO validate parameter values / instances (for value) are not available here / how to solve it?
                for param in action.parameters:
                    try:
                        PARAM_PLUGINS[param.type].value(TYPE_DEF_DICT, scene, project, action.id, param.id)
                    except ParameterPluginException:
                        problems.append(f"Parameter {param.id} of action {act.name} "
                                        f"has invalid value: '{param.value}'.")

    return problems


async def list_projects_cb(req: rpc.scene_project.ListProjectsRequest) -> \
        Union[rpc.scene_project.ListProjectsResponse, hlp.RPC_RETURN_TYPES]:

    data: List[rpc.scene_project.ListProjectsResponseData] = []

    projects = await storage.get_projects()

    scenes: Dict[str, Scene] = {}

    for project_iddesc in projects.items:

        try:
            project = await storage.get_project(project_iddesc.id)
        except Arcor2Exception as e:
            await logger.warning(f"Ignoring project {project_iddesc.id} due to error: {e}")
            continue

        pd = rpc.scene_project.ListProjectsResponseData(id=project.id, desc=project.desc)
        data.append(pd)

        if project.scene_id not in scenes:
            try:
                scenes[project.scene_id] = await storage.get_scene(project.scene_id)
            except PersistentStorageException:
                pd.problems.append("Scene does not exist.")
                continue

        pd.problems = project_problems(scenes[project.scene_id], project)
        pd.valid = not pd.problems

        if not pd.valid:
            continue

        try:
            program_src(project, scenes[project.scene_id], otu.built_in_types_names())
            pd.executable = True
        except SourceException as e:
            pd.problems.append(str(e))

    return rpc.scene_project.ListProjectsResponse(data=data)


async def list_scenes_cb(req: rpc.scene_project.ListScenesRequest) -> \
        Union[rpc.scene_project.ListScenesResponse, hlp.RPC_RETURN_TYPES]:

    scenes = await storage.get_scenes()
    return rpc.scene_project.ListScenesResponse(data=scenes.items)


async def list_meshes_cb(req: rpc.storage.ListMeshesRequest) -> Union[rpc.storage.ListMeshesResponse,
                                                                      hlp.RPC_RETURN_TYPES]:
    return rpc.storage.ListMeshesResponse(data=await storage.get_meshes())


async def new_object_type_cb(req: rpc.objects.NewObjectTypeRequest) -> Union[rpc.objects.NewObjectTypeResponse,
                                                                             hlp.RPC_RETURN_TYPES]:

    meta = req.args

    if meta.type in OBJECT_TYPES:
        return False, "Object type already exists."

    if meta.base not in OBJECT_TYPES:
        return False, f"Unknown base object type '{meta.base}', known types are: {', '.join(OBJECT_TYPES.keys())}."

    if not hlp.is_valid_type(meta.type):
        return False, "Object type invalid (should be CamelCase)."

    obj = meta.to_object_type()
    obj.source = new_object_type_source(OBJECT_TYPES[meta.base], meta)

    if meta.object_model and meta.object_model.type != ModelTypeEnum.MESH:
        assert meta.type == meta.object_model.model().id
        await storage.put_model(meta.object_model.model())

    # TODO check whether mesh id exists - if so, then use existing mesh, if not, upload a new one
    if meta.object_model and meta.object_model.type == ModelTypeEnum.MESH:
        # ...get whole mesh (focus_points) based on mesh id
        assert meta.object_model.mesh
        try:
            meta.object_model.mesh = await storage.get_mesh(meta.object_model.mesh.id)
        except storage.PersistentStorageException as e:
            await logger.error(e)
            return False, f"Mesh ID {meta.object_model.mesh.id} does not exist."

    await storage.update_object_type(obj)

    OBJECT_TYPES[meta.type] = meta
    ACTIONS[meta.type] = otu.object_actions(TYPE_TO_PLUGIN,
                                            hlp.type_def_from_source(obj.source, obj.id, Generic), obj.source)
    otu.add_ancestor_actions(meta.type, ACTIONS, OBJECT_TYPES)

    asyncio.ensure_future(notify(ObjectTypesChangedEvent(data=[meta.type])))
    return None


@scene_needed
@no_project
async def focus_object_start_cb(req: rpc.objects.FocusObjectStartRequest) -> Union[rpc.objects.FocusObjectStartResponse,
                                                                                   hlp.RPC_RETURN_TYPES]:

    global FOCUS_OBJECT
    global FOCUS_OBJECT_ROBOT

    obj_id = req.args.object_id

    if obj_id in FOCUS_OBJECT_ROBOT:
        return False, "Focusing already started."

    if obj_id not in SCENE_OBJECT_INSTANCES:
        return False, "Unknown object."

    try:
        inst = await get_robot_instance(req.args.robot.robot_id, req.args.robot.end_effector)
    except Arcor2Exception as e:
        return False, str(e)

    if not ROBOT_META[inst.__class__.__name__].features.focus:
        return False, "Robot/service does not support focusing."

    obj_type = OBJECT_TYPES[get_obj_type_name(obj_id)]

    if not obj_type.object_model or obj_type.object_model.type != ModelTypeEnum.MESH:
        return False, "Only available for objects with mesh model."

    assert obj_type.object_model.mesh

    focus_points = obj_type.object_model.mesh.focus_points

    if not focus_points:
        return False, "focusPoints not defined for the mesh."

    FOCUS_OBJECT_ROBOT[req.args.object_id] = req.args.robot
    FOCUS_OBJECT[obj_id] = {}
    await logger.info(f'Start of focusing for {obj_id}.')
    return None


def get_obj_type_name(object_id: str) -> str:

    return SCENE_OBJECT_INSTANCES[object_id].__class__.__name__


@no_project
async def focus_object_cb(req: rpc.objects.FocusObjectRequest) -> Union[rpc.objects.FocusObjectResponse,
                                                                        hlp.RPC_RETURN_TYPES]:

    obj_id = req.args.object_id
    pt_idx = req.args.point_idx

    if obj_id not in SCENE_OBJECT_INSTANCES:
        return False, "Unknown object_id."

    obj_type = OBJECT_TYPES[get_obj_type_name(obj_id)]

    assert obj_type.object_model and obj_type.object_model.mesh

    focus_points = obj_type.object_model.mesh.focus_points

    assert focus_points

    if pt_idx < 0 or pt_idx > len(focus_points)-1:
        return False, "Index out of range."

    if obj_id not in FOCUS_OBJECT:
        await logger.info(f'Start of focusing for {obj_id}.')
        FOCUS_OBJECT[obj_id] = {}

    robot_id, end_effector = FOCUS_OBJECT_ROBOT[obj_id].as_tuple()

    FOCUS_OBJECT[obj_id][pt_idx] = await get_end_effector_pose(robot_id, end_effector)

    r = rpc.objects.FocusObjectResponse()
    r.data.finished_indexes = list(FOCUS_OBJECT[obj_id].keys())
    return r


async def get_robot_instance(robot_id: str, end_effector_id: Optional[str] = None) -> Union[Robot, RobotService]:

    if robot_id in SCENE_OBJECT_INSTANCES:
        robot_inst = SCENE_OBJECT_INSTANCES[robot_id]
        if not isinstance(robot_inst, Robot):
            raise Arcor2Exception("Not a robot.")
        if end_effector_id and end_effector_id not in await hlp.run_in_executor(robot_inst.get_end_effectors_ids):
            raise Arcor2Exception("Unknown end effector ID.")
        return robot_inst
    else:
        robot_srv_inst = find_robot_service()
        if not robot_srv_inst or robot_id not in await hlp.run_in_executor(robot_srv_inst.get_robot_ids):
            raise Arcor2Exception("Unknown robot ID.")
        if end_effector_id and end_effector_id not in await hlp.run_in_executor(robot_srv_inst.get_end_effectors_ids,
                                                                                robot_id):
            raise Arcor2Exception("Unknown end effector ID.")
        return robot_srv_inst


@scene_needed
@no_project
async def focus_object_done_cb(req: rpc.objects.FocusObjectDoneRequest) -> Union[rpc.objects.FocusObjectDoneResponse,
                                                                                 hlp.RPC_RETURN_TYPES]:

    global FOCUS_OBJECT
    global FOCUS_OBJECT_ROBOT

    obj_id = req.args.id

    if obj_id not in FOCUS_OBJECT:
        return False, "focusObjectStart/focusObject has to be called first."

    obj_type = OBJECT_TYPES[get_obj_type_name(obj_id)]

    assert obj_type.object_model and obj_type.object_model.mesh

    focus_points = obj_type.object_model.mesh.focus_points

    assert focus_points

    if len(FOCUS_OBJECT[obj_id]) < len(focus_points):
        return False, "Not all points were done."

    robot_id, end_effector = FOCUS_OBJECT_ROBOT[obj_id].as_tuple()
    robot_inst = await get_robot_instance(robot_id)
    assert hasattr(robot_inst, "focus")  # mypy does not deal with hasattr

    assert SCENE

    obj = get_scene_object(SCENE, obj_id)

    fp: List[Position] = []
    rp: List[Position] = []

    for idx, pose in FOCUS_OBJECT[obj_id].items():

        fp.append(focus_points[idx].position)
        rp.append(pose.position)

    mfa = MeshFocusAction(fp, rp)

    await logger.debug(f'Attempt to focus for object {obj_id}, data: {mfa}')

    try:
        obj.pose = await hlp.run_in_executor(robot_inst.focus, mfa)  # type: ignore
    except Arcor2Exception as e:
        await logger.error(f"Focus failed with: {e}, mfa: {mfa}.")
        return False, "Focusing failed."

    await logger.info(f"Done focusing for {obj_id}.")

    clean_up_after_focus(obj_id)

    asyncio.ensure_future(notify_scene_change_to_others())
    asyncio.ensure_future(scene_object_pose_updated(SCENE.id, obj.id))
    return None


async def scene_object_pose_updated(scene_id: str, obj_id: str) -> None:

    async for project in projects_using_object(scene_id, obj_id):

        for obj in project.objects:
            if obj.id != obj_id:
                continue
            for ap in obj.action_points:
                for joints in ap.robot_joints:
                    joints.is_valid = False

        await storage.update_project(project)


def clean_up_after_focus(obj_id: str) -> None:

    try:
        del FOCUS_OBJECT[obj_id]
    except KeyError:
        pass

    try:
        del FOCUS_OBJECT_ROBOT[obj_id]
    except KeyError:
        pass


async def register(websocket) -> None:

    await logger.info("Registering new ui")
    INTERFACES.add(websocket)

    await notify_scene(websocket)
    await notify_project(websocket)

    # TODO avoid cast
    resp = cast(rpc.execution.ProjectStateResponse,
                await manager_request(rpc.execution.ProjectStateRequest(id=uuid.uuid4().int)))  # type: ignore

    await asyncio.wait([websocket.send(ProjectStateEvent(data=resp.data.project).to_json())])
    if resp.data.action:
        await asyncio.wait([websocket.send(ActionStateEvent(data=resp.data.action).to_json())])
    if resp.data.action_args:
        await asyncio.wait([websocket.send(CurrentActionEvent(data=resp.data.action_args).to_json())])


async def unregister(websocket) -> None:
    await logger.info("Unregistering ui")  # TODO print out some identifier
    INTERFACES.remove(websocket)


async def collision(obj: Generic,
                    rs: Optional[RobotService] = None, *, add: bool = False, remove: bool = False) -> None:
    """

    :param obj: Instance of the object.
    :param add:
    :param remove:
    :param rs:
    :return:
    """

    assert add ^ remove

    if not obj.collision_model:
        return

    if rs is None:
        rs = find_robot_service()
    if rs:
        try:
            # TODO notify user somehow when something went wrong?
            await hlp.run_in_executor(rs.add_collision if add else rs.remove_collision, obj)
        except Arcor2Exception as e:
            await logger.error(e)


async def add_object_to_scene(obj: SceneObject, add_to_scene=True, srv_obj_ok=False) -> Tuple[bool, str]:
    """

    :param obj:
    :param add_to_scene: Set to false to only create object instance and add its collision model (if any).
    :return:
    """

    assert SCENE

    if obj.type not in OBJECT_TYPES:
        # TODO try to get it from storage
        return False, "Unknown object type."

    obj_meta = OBJECT_TYPES[obj.type]

    if srv_obj_ok:  # just for internal usage

        if not obj_meta.needs_services <= SERVICE_TYPES.keys():
            return False, "Some of required services is not available."

        if not obj_meta.needs_services <= SERVICES_INSTANCES.keys():
            return False, "Some of required services is not in the scene."

    elif obj_meta.needs_services:
        return False, "Service(s)-based object."

    if obj_meta.abstract:
        return False, "Cannot instantiate abstract type."

    if obj.id in SCENE_OBJECT_INSTANCES or obj.id in SERVICES_INSTANCES:
        return False, "Object/service with that id already exists."

    if not hlp.is_valid_identifier(obj.id):
        return False, "Object ID invalid (should be snake_case)."

    await logger.debug(f"Creating instance {obj.id} ({obj.type}).")

    try:

        if obj.type in otu.built_in_types_names():
            cls = otu.get_built_in_type(obj.type)
        else:
            obj_type = await storage.get_object_type(obj.type)
            cls = hlp.type_def_from_source(obj_type.source, obj_type.id, Generic)

        coll_model: Optional[Models] = None
        if obj_meta.object_model:
            coll_model = obj_meta.object_model.model()

        if not obj_meta.needs_services:
            obj_inst = cls(obj.id, obj.pose, coll_model)
        else:

            srv_args: List[Service] = []

            for name, ttype in get_type_hints(cls.__init__).items():

                # service arguments should be listed first
                if not issubclass(ttype, Service):
                    break

                try:
                    srv_args.append(SERVICES_INSTANCES[ttype.__name__])
                except KeyError:
                    return False, f"Object type {obj.type} has invalid typ annotation in the constructor, " \
                                  f"service {ttype.__name__} not available."

            try:
                obj_inst = cls(*srv_args, obj.id, obj.pose, coll_model)  # type: ignore
            except TypeError as e:
                return False, f"System error ({e})."

        SCENE_OBJECT_INSTANCES[obj.id] = obj_inst

        if add_to_scene:
            SCENE.objects.append(obj)

        await collision(obj_inst, add=True)

    except Arcor2Exception as e:
        await logger.error(e)
        return False, "System error"

    return True, "ok"


async def auto_add_object_to_scene(obj_type_name: str) -> Tuple[bool, str]:

    assert SCENE

    if obj_type_name not in OBJECT_TYPES:
        return False, "Unknown object type."

    if obj_type_name in otu.built_in_types_names():
        return False, "Does not work for built in types."

    obj_meta = OBJECT_TYPES[obj_type_name]

    if not obj_meta.needs_services:
        return False, "Ordinary object."

    if obj_meta.abstract:
        return False, "Cannot instantiate abstract type."

    if not obj_meta.needs_services <= SERVICE_TYPES.keys():
        return False, "Some of required services is not available."

    if not obj_meta.needs_services <= SERVICES_INSTANCES.keys():
        return False, "Some of required services is not in the scene."

    try:

        obj_type = await storage.get_object_type(obj_type_name)
        cls = hlp.type_def_from_source(obj_type.source, obj_type.id, Generic)

        args: List[Service] = [SERVICES_INSTANCES[srv_name] for srv_name in obj_meta.needs_services]

        assert hasattr(cls, otu.SERVICES_METHOD_NAME)
        for obj_inst in cls.from_services(*args):  # type: ignore

            assert isinstance(obj_inst, Generic)

            if not hlp.is_valid_identifier(obj_inst.id):
                # TODO add message to response
                await logger.warning(f"Object id {obj_inst.id} invalid.")
                continue

            if obj_inst.id in SCENE_OBJECT_INSTANCES:
                await logger.warning(f"Object id {obj_inst.id} already in scene.")
                continue

            SCENE_OBJECT_INSTANCES[obj_inst.id] = obj_inst
            SCENE.objects.append(obj_inst.scene_object())

            if obj_meta.object_model:
                obj_inst.collision_model = obj_meta.object_model.model()
                await collision(obj_inst, add=True)

    except Arcor2Exception as e:
        await logger.error(e)
        return False, "System error"

    return True, "ok"


@scene_needed
@no_project
async def add_object_to_scene_cb(req: rpc.scene_project.AddObjectToSceneRequest) -> \
        Union[rpc.scene_project.AddObjectToSceneResponse, hlp.RPC_RETURN_TYPES]:

    obj = req.args
    res, msg = await add_object_to_scene(obj)

    if not res:
        return res, msg

    asyncio.ensure_future(notify_scene_change_to_others())
    return None


@scene_needed
@no_project
async def auto_add_object_to_scene_cb(req: rpc.scene_project.AutoAddObjectToSceneRequest) -> \
        Union[rpc.scene_project.AutoAddObjectToSceneResponse, hlp.RPC_RETURN_TYPES]:

    obj = req.args
    res, msg = await auto_add_object_to_scene(obj.type)

    if not res:
        return res, msg

    asyncio.ensure_future(notify_scene_change_to_others())
    return None


def find_robot_service() -> Union[None, RobotService]:

    for srv in SERVICES_INSTANCES.values():
        if isinstance(srv, RobotService):
            return srv
    else:
        return None


async def add_service_to_scene(srv: SceneService) -> Tuple[bool, str]:

    if srv.type not in SERVICE_TYPES:
        return False, "Unknown service type."

    if srv.type in SERVICES_INSTANCES:
        return False, "Service already in scene."

    srv_type = await storage.get_service_type(srv.type)

    cls_def = hlp.type_def_from_source(srv_type.source, srv_type.id, Service)

    if issubclass(cls_def, RobotService) and find_robot_service():
        return False, "Scene might contain only one robot service."

    try:
        srv_inst = await hlp.run_in_executor(cls_def, srv.configuration_id)
    except Arcor2Exception as e:
        await logger.error(e)
        return False, "System error"

    SERVICES_INSTANCES[srv.type] = srv_inst

    if isinstance(srv_inst, RobotService):
        await logger.info("RobotService added, adding collision models to all objects.")
        for obj_inst in SCENE_OBJECT_INSTANCES.values():
            await collision(obj_inst, srv_inst, add=True)

    return True, "ok"


@scene_needed
@no_project
async def add_service_to_scene_cb(req: rpc.scene_project.AddServiceToSceneRequest) ->\
        Union[rpc.scene_project.AddServiceToSceneResponse, hlp.RPC_RETURN_TYPES]:

    assert SCENE

    srv = req.args
    res, msg = await add_service_to_scene(srv)

    if not res:
        return res, msg

    SCENE.services.append(srv)
    asyncio.ensure_future(notify_scene_change_to_others())
    return None


async def projects_using_object(scene_id: str, obj_id: str) -> AsyncIterator[Project]:

    id_list = await storage.get_projects()

    for project_meta in id_list.items:

        project = await storage.get_project(project_meta.id)

        if project.scene_id != scene_id:
            continue

        for obj in project.objects:

            if obj.id == obj_id:
                yield project
                break

            for ap in obj.action_points:
                for action in ap.actions:
                    action_obj_id, _ = action.parse_type()

                    if action_obj_id == obj_id:
                        yield project
                        break


@scene_needed
async def scene_object_usage_request_cb(req: rpc.scene_project.SceneObjectUsageRequest) -> \
        Union[rpc.scene_project.SceneObjectUsageResponse, hlp.RPC_RETURN_TYPES]:
    """
    Works for both services and objects.
    :param req:
    :return:
    """

    assert SCENE

    if not (any(obj.id == req.args.id for obj in SCENE.objects) or
            any(srv.type == req.args.id for srv in SCENE.services)):
        return False, "Unknown ID."

    resp = rpc.scene_project.SceneObjectUsageResponse()

    async for project in projects_using_object(SCENE.id, req.args.id):
        resp.data.add(project.id)

    return resp


@scene_needed
async def action_param_values_cb(req: rpc.objects.ActionParamValuesRequest) -> \
        Union[rpc.objects.ActionParamValuesResponse, hlp.RPC_RETURN_TYPES]:

    inst: Union[None, Service, Generic] = None

    # TODO method to get object/service based on ID
    if req.args.id in SCENE_OBJECT_INSTANCES:
        inst = SCENE_OBJECT_INSTANCES[req.args.id]
    elif req.args.id in SERVICES_INSTANCES:
        inst = SERVICES_INSTANCES[req.args.id]
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
        await logger.error(f"Unable to get values for parameter {req.args.param_id}, "
                           f"object/service {inst.id} has no method named {method_name}.")
        return False, "System error."

    # TODO update hlp.run_in_executor to support kwargs
    resp.data = await asyncio.get_event_loop().run_in_executor(None, functools.partial(method, **parent_params))
    return resp


@scene_needed
@no_project
async def remove_from_scene_cb(req: rpc.scene_project.RemoveFromSceneRequest) -> \
        Union[rpc.scene_project.RemoveFromSceneResponse, hlp.RPC_RETURN_TYPES]:

    assert SCENE

    if req.args.id in SCENE_OBJECT_INSTANCES:

        SCENE.objects = [obj for obj in SCENE.objects if obj.id != req.args.id]
        obj_inst = SCENE_OBJECT_INSTANCES[req.args.id]
        await collision(obj_inst, remove=True)
        del SCENE_OBJECT_INSTANCES[req.args.id]

    elif req.args.id in SERVICES_INSTANCES:

        # first check if some object is not using it
        for obj in SCENE.objects:
            if req.args.id in OBJECT_TYPES[obj.type].needs_services:
                return False, f"Object {obj.id} ({obj.type}) relies on the service to be removed: {req.args.id}."

        SCENE.services = [srv for srv in SCENE.services if srv.type != req.args.id]
        del SERVICES_INSTANCES[req.args.id]

    else:
        return False, "Unknown id."

    asyncio.ensure_future(remove_object_references_from_projects(req.args.id))
    asyncio.ensure_future(notify_scene_change_to_others())
    return None


async def get_robot_meta_cb(req: rpc.robot.GetRobotMetaRequest) -> Union[rpc.robot.GetRobotMetaResponse,
                                                                         hlp.RPC_RETURN_TYPES]:

    return rpc.robot.GetRobotMetaResponse(data=list(ROBOT_META.values()))


async def system_info_cb(req: rpc.common.SystemInfoRequest) -> Union[rpc.common.SystemInfoResponse,
                                                                     hlp.RPC_RETURN_TYPES]:

    resp = rpc.common.SystemInfoResponse()
    resp.data.version = arcor2.version()
    resp.data.api_version = arcor2.api_version()
    return resp


async def build_project_cb(req: rpc.execution.BuildProjectRequest) -> \
        Union[rpc.execution.BuildProjectResponse, hlp.RPC_RETURN_TYPES]:

    # call build service
    # TODO store data in memory
    with tempfile.TemporaryDirectory() as tmpdirname:

        path = os.path.join(tmpdirname, "publish.zip")

        try:
            await hlp.run_in_executor(rest.download, f"{BUILDER_URL}/project/{req.args.id}/publish", path)
        except rest.RestException as e:
            await logger.error(e)
            return False, "Failed to get project package."

        with open(path, "rb") as zip_file:
            b64_bytes = base64.b64encode(zip_file.read())
            b64_str = b64_bytes.decode()

    # send data to execution service
    exe_req = rpc.execution.UploadPackageRequest(uuid.uuid4().int,
                                                 args=rpc.execution.UploadPackageArgs(req.args.id, b64_str))
    resp = await manager_request(exe_req)
    return resp.result, " ".join(resp.messages) if resp.messages else ""


@scene_needed
@project_needed
async def execute_action_cb(req: rpc.scene_project.ExecuteActionRequest) -> \
        Union[rpc.scene_project.ExecuteActionResponse, hlp.RPC_RETURN_TYPES]:

    assert SCENE and PROJECT

    global RUNNING_ACTION

    if RUNNING_ACTION:
        return False, f"Action {RUNNING_ACTION} is being executed. Only one action can be executed at a time."

    try:
        action = PROJECT.action(req.args.action_id)
    except Arcor2Exception:
        return False, "Unknown action."

    params: Dict[str, Any] = {}

    for param in action.parameters:
        try:
            params[param.id] = PARAM_PLUGINS[param.type].value(TYPE_DEF_DICT, SCENE, PROJECT, action.id, param.id)
        except ParameterPluginException as e:
            await logger.error(e)
            return False, f"Failed to get value for parameter {param.id}."

    obj_id, action_name = action.parse_type()

    obj: Optional[Union[Generic, Service]] = None

    if obj_id in SCENE_OBJECT_INSTANCES:
        obj = SCENE_OBJECT_INSTANCES[obj_id]
    elif obj_id in SERVICES_INSTANCES:
        obj = SERVICES_INSTANCES[obj_id]
    else:
        return False, "Internal error: project not in sync with scene."

    if not hasattr(obj, action_name):
        return False, "Internal error: object does not have the requested method."

    RUNNING_ACTION = action.id

    # schedule execution and return success
    asyncio.ensure_future(execute_action(getattr(obj, action_name), params))
    return None


async def execute_action(action_method: Callable, params: Dict[str, Any]) -> None:

    global RUNNING_ACTION

    try:
        await hlp.run_in_executor(action_method, *params.values())
    except (Arcor2Exception, TypeError) as e:
        await logger.error(e)

    # TODO send event with results
    RUNNING_ACTION = None


async def remove_object_references_from_projects(obj_id: str) -> None:

    assert SCENE

    updated_project_ids: Set[str] = set()

    async for project in projects_using_object(SCENE.id, obj_id):

        # delete object and its action points
        project.objects = [obj for obj in project.objects if obj.id != obj_id]

        action_ids: Set[str] = set()

        for obj in project.objects:
            for ap in obj.action_points:

                # delete actions using the object
                ap.actions = [act for act in ap.actions if act.parse_type()[0] != obj_id]

                # delete actions using obj's action points as parameters
                # TODO fix this!
                """
                actions_using_invalid_param: Set[str] = \
                    {act.id for act in ap.actions for param in act.parameters
                     if param.type in (ActionParameterTypeEnum.JOINTS, ActionParameterTypeEnum.POSE) and
                     param.value.startswith(obj_id)}

                ap.actions = [act for act in ap.actions if act.id not in actions_using_invalid_param]

                # get IDs of remaining actions
                action_ids.update({act.id for act in ap.actions})
                """

        valid_ids: Set[str] = action_ids | ActionIOEnum.set()

        # remove invalid inputs/outputs
        for obj in project.objects:
            for ap in obj.action_points:
                for act in ap.actions:
                    act.inputs = [input for input in act.inputs if input.default in valid_ids]
                    act.outputs = [output for output in act.outputs if output.default in valid_ids]

        await storage.update_project(project)
        updated_project_ids.add(project.id)

    await logger.info("Updated projects: {}".format(updated_project_ids))


async def scene_change(ui, event: SceneChangedEvent) -> None:

    global SCENE

    if PROJECT:
        await logger.warning("Scene changes not allowed when editing project.")
        return

    if event.data:
        for srv in event.data.services:
            if srv.type not in SERVICES_INSTANCES:
                await notify_scene(ui)
                await logger.warning("Ignoring scene changes: service added.")
                return

        # TODO don't allow change of pose for robots
        for obj in event.data.objects:
            if obj.id not in SCENE_OBJECT_INSTANCES:
                await notify_scene(ui)
                await logger.warning("Ignoring scene changes: object added.")
                return
    else:
        await logger.info("Clearing the scene.")
        rs = find_robot_service()
        if rs:
            for obj_inst in SCENE_OBJECT_INSTANCES.values():
                await collision(obj_inst, rs, remove=True)
        SCENE_OBJECT_INSTANCES.clear()
        SERVICES_INSTANCES.clear()

    SCENE = event.data
    await notify_scene_change_to_others(ui)


async def project_change(ui, event: ProjectChangedEvent) -> None:

    global PROJECT

    PROJECT = event.data

    await notify_project_change_to_others(ui)


RPC_DICT: hlp.RPC_DICT_TYPE = {
    rpc.common.SystemInfoRequest: system_info_cb,
    rpc.execution.BuildProjectRequest: build_project_cb,
    rpc.objects.GetObjectTypesRequest: get_object_types_cb,
    rpc.objects.GetActionsRequest: get_object_actions_cb,
    rpc.objects.UpdateActionPointPoseRequest: update_action_point_cb,
    rpc.objects.UpdateActionPointJointsRequest: update_ap_joints_cb,
    rpc.objects.UpdateActionObjectPoseRequest: update_action_object_cb,
    rpc.objects.NewObjectTypeRequest: new_object_type_cb,
    rpc.objects.FocusObjectRequest: focus_object_cb,
    rpc.objects.FocusObjectStartRequest: focus_object_start_cb,
    rpc.objects.FocusObjectDoneRequest: focus_object_done_cb,
    rpc.objects.ActionParamValuesRequest: action_param_values_cb,
    rpc.robot.GetRobotMetaRequest: get_robot_meta_cb,
    rpc.scene_project.SaveProjectRequest: save_project_cb,
    rpc.scene_project.SaveSceneRequest: save_scene_cb,
    rpc.scene_project.OpenProjectRequest: open_project_cb,
    rpc.scene_project.ListProjectsRequest: list_projects_cb,
    rpc.scene_project.ListScenesRequest: list_scenes_cb,
    rpc.scene_project.AddObjectToSceneRequest: add_object_to_scene_cb,
    rpc.scene_project.AutoAddObjectToSceneRequest: auto_add_object_to_scene_cb,
    rpc.scene_project.AddServiceToSceneRequest: add_service_to_scene_cb,
    rpc.scene_project.RemoveFromSceneRequest: remove_from_scene_cb,
    rpc.scene_project.SceneObjectUsageRequest: scene_object_usage_request_cb,
    rpc.scene_project.OpenSceneRequest: open_scene_cb,
    rpc.scene_project.ExecuteActionRequest: execute_action_cb,
    rpc.services.GetServicesRequest: get_services_cb,
    rpc.storage.ListMeshesRequest: list_meshes_cb
}

# add Project Manager RPC API
for k, v in nodes.execution.RPC_DICT.items():

    if v.__name__.startswith("_"):
        continue

    RPC_DICT[k] = manager_request


EVENT_DICT: hlp.EVENT_DICT_TYPE = {
    SceneChangedEvent: scene_change,
    ProjectChangedEvent: project_change
}


def main():

    assert sys.version_info >= (3, 8)

    parser = argparse.ArgumentParser()

    parser.add_argument("-v", "--verbose", help="Increase output verbosity",
                        action="store_const", const=LogLevel.DEBUG, default=LogLevel.INFO)
    parser.add_argument('--version', action='version', version=arcor2.version(),
                        help="Shows ARCOR2 version and exits.")
    parser.add_argument('--api_version', action='version', version=arcor2.api_version(),
                        help="Shows API version and exits.")
    parser.add_argument("-a", "--asyncio_debug", help="Turn on asyncio debug mode.",
                        action="store_const", const=True, default=False)

    args = parser.parse_args()
    logger.level = args.verbose

    loop = asyncio.get_event_loop()
    loop.set_debug(enabled=args.asyncio_debug)

    loop.run_until_complete(asyncio.wait([asyncio.gather(project_manager_client(), _initialize_server())]))


if __name__ == "__main__":
    main()
