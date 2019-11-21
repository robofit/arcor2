#!/usr/bin/env python3
# -*- coding: utf-8 -*-


import asyncio
import json
import functools
import sys
from typing import Dict, Set, Union, TYPE_CHECKING, Tuple, Optional, List, Callable, cast, AsyncIterator
import uuid
import keyword

import websockets
from websockets.server import WebSocketServerProtocol
from aiologger import Logger  # type: ignore

from arcor2.source.logic import program_src
from arcor2.source.object_types import new_object_type_source
from arcor2.source import SourceException
from arcor2.nodes.manager import RPC_DICT as MANAGER_RPC_DICT, PORT as MANAGER_PORT
from arcor2 import service_types_utils as stu, object_types_utils as otu, helpers as hlp
from arcor2.data.common import Scene, Project, Pose, Position, SceneObject, SceneService, ActionIOEnum,\
    ActionParameterTypeEnum
from arcor2.data.object_type import ObjectActionsDict, ObjectTypeMetaDict, ObjectTypeMeta, ModelTypeEnum, \
    MeshFocusAction, ObjectModel, Models
from arcor2.data.services import ServiceTypeMeta
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

if TYPE_CHECKING:
    ReqQueue = asyncio.Queue[rpc.Request]
    RespQueue = asyncio.Queue[rpc.Response]
else:
    ReqQueue = asyncio.Queue
    RespQueue = asyncio.Queue


logger = Logger.with_default_handlers(name='server', formatter=hlp.aiologger_formatter())

SCENE: Union[Scene, None] = None
PROJECT: Union[Project, None] = None

INTERFACES: Set[WebSocketServerProtocol] = set()

MANAGER_RPC_REQUEST_QUEUE: ReqQueue = ReqQueue()
MANAGER_RPC_RESPONSES: Dict[int, RespQueue] = {}

OBJECT_TYPES: ObjectTypeMetaDict = {}
SERVICE_TYPES: Dict[str, ServiceTypeMeta] = {}

SCENE_OBJECT_INSTANCES: Dict[str, Generic] = {}
SERVICES_INSTANCES: Dict[str, Service] = {}

ACTIONS: ObjectActionsDict = {}  # used for actions of both object_types / services

FOCUS_OBJECT: Dict[str, Dict[int, Pose]] = {}  # object_id / idx, pose
FOCUS_OBJECT_ROBOT: Dict[str, Tuple[str, str]] = {}  # object_id / robot, end_effector


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
            async with websockets.connect(f"ws://localhost:{MANAGER_PORT}") as manager_client:

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

    await asyncio.wait([_get_object_types(), _get_service_types()])
    await asyncio.wait([_get_object_actions(), _check_manager()])


async def _get_service_types() -> None:

    global SERVICE_TYPES

    service_types: Dict[str, ServiceTypeMeta] = {}

    srv_ids = await storage.get_service_type_ids()

    for srv_id in srv_ids.items:

        srv_type = await storage.get_service_type(srv_id.id)
        try:
            service_types[srv_id.id] = stu.meta_from_def(hlp.type_def_from_source(srv_type.source, srv_type.id, Service))
        except Arcor2Exception as e:
            await logger.error(f"Ignoring object type {srv_type.id}: {e}")

    SERVICE_TYPES = service_types


async def _get_object_types() -> None:

    global OBJECT_TYPES

    object_types: Dict[str, ObjectTypeMeta] = otu.built_in_types_meta()

    obj_ids = await storage.get_object_type_ids()

    for obj_id in obj_ids.items:
        obj = await storage.get_object_type(obj_id.id)
        try:
            object_types[obj.id] = otu.meta_from_def(hlp.type_def_from_source(obj.source, obj.id, Generic))
        except (otu.ObjectTypeException, hlp.TypeDefException) as e:
            await logger.error(f"Ignoring object type {obj.id}: {e}")
            continue

        if obj.model:
            model = await storage.get_model(obj.model.id, obj.model.type)
            kwargs = {model.type().value.lower(): model}
            object_types[obj.id].object_model = ObjectModel(model.type(), **kwargs)  # type: ignore

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


async def get_object_types_cb(req: rpc.GetObjectTypesRequest) -> rpc.GetObjectTypesResponse:
    return rpc.GetObjectTypesResponse(data=list(OBJECT_TYPES.values()))


async def get_services_cb(req: rpc.GetServicesRequest) -> rpc.GetServicesResponse:
    return rpc.GetServicesResponse(data=list(SERVICE_TYPES.values()))


@scene_needed
@no_project
async def save_scene_cb(req: rpc.SaveSceneRequest) -> Union[rpc.SaveSceneResponse, hlp.RPC_RETURN_TYPES]:

    assert SCENE
    await storage.update_scene(SCENE)
    return None


@scene_needed
@project_needed
async def save_project_cb(req: rpc.SaveProjectRequest) -> Union[rpc.SaveProjectResponse, hlp.RPC_RETURN_TYPES]:

    assert SCENE and PROJECT
    await storage.update_project(PROJECT)
    return None


async def open_scene(scene_id: str):

    global SCENE
    SCENE = await storage.get_scene(scene_id)

    for srv in SCENE.services:
        await add_service_to_scene(srv)

    for obj in SCENE.objects:
        await add_object_to_scene(obj, add_to_scene=False)

    asyncio.ensure_future(notify_scene_change_to_others())


async def open_project(project_id: str) -> None:

    global PROJECT

    PROJECT = await storage.get_project(project_id)
    await open_scene(PROJECT.scene_id)
    asyncio.ensure_future(notify_project_change_to_others())


@no_project
async def open_scene_cb(req: rpc.OpenSceneRequest) -> Union[rpc.OpenSceneResponse, hlp.RPC_RETURN_TYPES]:

    await open_scene(req.args.id)
    return None


async def open_project_cb(req: rpc.OpenProjectRequest) -> Union[rpc.OpenProjectResponse, hlp.RPC_RETURN_TYPES]:

    # TODO validate using project_problems?
    await open_project(req.args.id)
    return None


async def _get_object_actions() -> None:  # TODO do it in parallel

    global ACTIONS

    object_actions_dict: ObjectActionsDict = otu.built_in_types_actions()

    for obj_type, obj in OBJECT_TYPES.items():

        if obj.built_in:  # built-in types are already there
            continue

        # db-stored (user-created) object types
        obj_db = await storage.get_object_type(obj_type)
        try:
            object_actions_dict[obj_type] = otu.object_actions(hlp.type_def_from_source(obj_db.source, obj_db.id, Generic))
        except hlp.TypeDefException as e:
            await logger.error(e)

    # add actions from ancestors
    for obj_type in OBJECT_TYPES.keys():
        otu.add_ancestor_actions(obj_type, object_actions_dict, OBJECT_TYPES)

    # get services' actions
    for service_type, service_meta in SERVICE_TYPES.items():
        srv_type = await storage.get_service_type(service_type)
        try:
            object_actions_dict[service_type] = otu.object_actions(
                hlp.type_def_from_source(srv_type.source, service_type, Service))
        except hlp.TypeDefException as e:
            await logger.warning(e)

    ACTIONS = object_actions_dict

    await notify(ObjectTypesChangedEvent(data=list(object_actions_dict.keys())))


async def _check_manager() -> None:
    """
    Loads project if it is loaded on manager
    :return:
    """

    # TODO avoid cast
    resp = cast(rpc.ProjectStateResponse, await manager_request(rpc.ProjectStateRequest(id=uuid.uuid4().int)))  # type: ignore

    if resp.data.id is not None and (PROJECT is None or PROJECT.id != resp.data.id):
        await open_project(resp.data.id)


async def get_object_actions_cb(req: rpc.GetActionsRequest) -> Union[rpc.GetActionsResponse, hlp.RPC_RETURN_TYPES]:

    try:
        return rpc.GetActionsResponse(data=ACTIONS[req.args.type])
    except KeyError:
        return False, f"Unknown object type: '{req.args.type}'."


async def manager_request(req: rpc.Request) -> rpc.Response:

    assert req.id not in MANAGER_RPC_RESPONSES

    MANAGER_RPC_RESPONSES[req.id] = RespQueue(maxsize=1)
    await MANAGER_RPC_REQUEST_QUEUE.put(req)

    resp = await MANAGER_RPC_RESPONSES[req.id].get()
    del MANAGER_RPC_RESPONSES[req.id]
    return resp


async def get_end_effector_pose(robot_id: str, end_effector: str) -> Pose:
    """
    :param robot_id:
    :param end_effector:
    :return: Global pose
    """

    if robot_id in SCENE_OBJECT_INSTANCES:

        robot = SCENE_OBJECT_INSTANCES[robot_id]

        if not isinstance(robot, Robot):
            raise RobotPoseException(f"Object {robot_id} is not instance of Robot!")

        if end_effector not in await hlp.run_in_executor(robot.get_end_effectors_ids):
            raise RobotPoseException(f"Unknown end effector.")

        try:
            return await hlp.run_in_executor(robot.get_end_effector_pose, end_effector)
        except NotImplementedError:
            raise RobotPoseException("The robot does not support getting pose.")

    else:

        for service in SERVICES_INSTANCES.values():
            if isinstance(service, RobotService) and robot_id in await hlp.run_in_executor(service.get_robot_ids):
                robot_service = service
                break
        else:
            raise RobotPoseException("Robot ID invalid or robot service not available.")

        if end_effector not in hlp.run_in_executor(robot_service.get_end_effectors_ids, robot_id):
            raise RobotPoseException(f"Unknown end effector.")

        try:
            return await hlp.run_in_executor(robot_service.get_end_effector_pose, robot_id, end_effector)
        except NotImplementedError:
            raise RobotPoseException("The robot does not support getting pose.")


@scene_needed
@project_needed
async def update_action_point_cb(req: rpc.UpdateActionPointPoseRequest) -> Union[rpc.UpdateActionPointPoseResponse,
                                                                             hlp.RPC_RETURN_TYPES]:

    assert SCENE and PROJECT

    try:
        proj_obj, ap = get_object_ap(PROJECT, req.args.id)
    except ActionPointNotFound:
        return False, "Invalid action point."

    try:
        new_pose = await get_end_effector_pose(req.args.robot.id, req.args.robot.end_effector)
    except RobotPoseException as e:
        return False, str(e)

    ap.pose = hlp.make_pose_rel(SCENE_OBJECT_INSTANCES[proj_obj.id].pose, new_pose)

    asyncio.ensure_future(notify_project_change_to_others())
    return None


@scene_needed
@no_project
async def update_action_object_cb(req: rpc.UpdateActionObjectPoseRequest) -> Union[rpc.UpdateActionObjectPoseRequest,
                                                                               hlp.RPC_RETURN_TYPES]:

    assert SCENE

    if req.args.id == req.args.robot.id:
        return False, "Robot cannot update its own pose."

    try:
        scene_object = get_scene_object(SCENE, req.args.id)
    except SceneObjectNotFound:
        return False, "Invalid action object."

    try:
        scene_object.pose = await get_end_effector_pose(req.args.robot.id, req.args.robot.end_effector)
    except RobotPoseException as e:
        return False, str(e)

    asyncio.ensure_future(notify_scene_change_to_others())
    return None


def project_problems(scene: Scene, project: Project) -> List[str]:

    scene_objects: Dict[str, str] = {obj.id: obj.type for obj in scene.objects}
    objects_aps: Dict[str, Set[str]] = {obj.id: {ap.id for ap in obj.action_points}
                                        for obj in project.objects}  # object_id, APs

    problems: List[str] = []

    for obj in project.objects:

        # test if all objects exists in scene
        if obj.id not in scene_objects:
            problems.append(f"Object ID {obj.id} does not exist in scene.")
            continue

        for ap in obj.action_points:

            for action in ap.actions:

                # check if objects have used actions
                obj_id, action_type = action.parse_type()

                if obj_id not in scene_objects:
                    problems.append(f"Object ID {obj.id} which action is used in {action.id} does not exist in scene.")
                    continue

                for act in ACTIONS[scene_objects[obj_id]]:
                    if action_type == act.name:
                        break
                else:
                    problems.append(f"Object type {scene_objects[obj_id]} does not have action {action_type} "
                                    f"used in {action.id}.")

                # check object's actions parameters
                action_params: Dict[str, ActionParameterTypeEnum] = \
                    {param.id: param.type for param in action.parameters}
                ot_params: Dict[str, ActionParameterTypeEnum] = {param.name: param.type for param in act.action_args
                                                                 for act in ACTIONS[scene_objects[obj_id]]}

                if action_params != ot_params:
                    problems.append(f"Action ID {action.id} of type {action.type} has invalid parameters.")

                # validate parameter values
                for param in action.parameters:
                    if param.type == ActionParameterTypeEnum.ACTION_POINT:

                        p_obj_id, p_ap_id = param.parse_value()

                        if p_obj_id not in objects_aps:
                            problems.append(f"Parameter {param.id} of action {action.id} refers to non-existent "
                                            f"object id.")

                        if p_ap_id not in objects_aps[p_obj_id]:
                            problems.append(f"Parameter {param.id} of action {action.id} refers to non-existent "
                                            f"action point of object id {p_obj_id}.")

                    # TODO validate values of another parameter types

    return problems


async def list_projects_cb(req: rpc.ListProjectsRequest) -> Union[rpc.ListProjectsResponse, hlp.RPC_RETURN_TYPES]:

    data: List[rpc.ListProjectsResponseData] = []

    projects = await storage.get_projects()

    scenes: Dict[str, Scene] = {}

    for project_iddesc in projects.items:

        project = await storage.get_project(project_iddesc.id)

        pd = rpc.ListProjectsResponseData(id=project.id, desc=project.desc)
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

    return rpc.ListProjectsResponse(data=data)


async def list_scenes_cb(req: rpc.ListScenesRequest) -> Union[rpc.ListScenesResponse, hlp.RPC_RETURN_TYPES]:

    scenes = await storage.get_scenes()
    return rpc.ListScenesResponse(data=scenes.items)


async def list_meshes_cb(req: rpc.ListMeshesRequest) -> Union[rpc.ListMeshesResponse, hlp.RPC_RETURN_TYPES]:
    return rpc.ListMeshesResponse(data=await storage.get_meshes())


async def new_object_type_cb(req: rpc.NewObjectTypeRequest) -> Union[rpc.NewObjectTypeResponse, hlp.RPC_RETURN_TYPES]:

    meta = req.args

    if meta.type in OBJECT_TYPES:
        return False, "Object type already exists."

    if meta.base not in OBJECT_TYPES:
        return False, "Unknown base object type."

    if not meta.type.isidentifier() or keyword.iskeyword(meta.type) \
            or meta.type != hlp.snake_case_to_camel_case(meta.type):
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
        meta.object_model.mesh = await storage.get_mesh(meta.object_model.mesh.id)

    await storage.update_object_type(obj)

    OBJECT_TYPES[meta.type] = meta
    ACTIONS[meta.type] = otu.object_actions(hlp.type_def_from_source(obj.source, obj.id, Generic))
    otu.add_ancestor_actions(meta.type, ACTIONS, OBJECT_TYPES)

    asyncio.ensure_future(notify(ObjectTypesChangedEvent(data=[meta.type])))
    return None


@scene_needed
@no_project
async def focus_object_start_cb(req: rpc.FocusObjectStartRequest) -> Union[rpc.FocusObjectStartResponse, hlp.RPC_RETURN_TYPES]:

    global FOCUS_OBJECT
    global FOCUS_OBJECT_ROBOT

    obj_id = req.args.object_id

    if obj_id in FOCUS_OBJECT_ROBOT:
        return False, "Focusing already started."

    if req.args.robot.id not in SCENE_OBJECT_INSTANCES:
        return False, "Unknown robot."

    if obj_id not in SCENE_OBJECT_INSTANCES:
        return False, "Unknown object."

    # TODO check if the robot supports (implements) focusing (how?)
    # TODO check if end effector exists

    obj_type = OBJECT_TYPES[get_obj_type_name(obj_id)]

    if not obj_type.object_model or obj_type.object_model.type != ModelTypeEnum.MESH:
        return False, "Only available for objects with mesh model."

    assert obj_type.object_model.mesh

    focus_points = obj_type.object_model.mesh.focus_points

    if not focus_points:
        return False, "focusPoints not defined for the mesh."

    FOCUS_OBJECT_ROBOT[req.args.object_id] = req.args.robot.as_tuple()
    FOCUS_OBJECT[obj_id] = {}
    await logger.info(f'Start of focusing for {obj_id}.')
    return None


def get_obj_type_name(object_id: str) -> str:

    return SCENE_OBJECT_INSTANCES[object_id].__class__.__name__


@no_project
async def focus_object_cb(req: rpc.FocusObjectRequest) -> Union[rpc.FocusObjectResponse, hlp.RPC_RETURN_TYPES]:

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

    robot_id, end_effector = FOCUS_OBJECT_ROBOT[obj_id]

    FOCUS_OBJECT[obj_id][pt_idx] = await get_end_effector_pose(robot_id, end_effector)

    r = rpc.FocusObjectResponse()
    r.data.finished_indexes = list(FOCUS_OBJECT[obj_id].keys())
    return r


@scene_needed
@no_project
async def focus_object_done_cb(req: rpc.FocusObjectDoneRequest) -> Union[rpc.FocusObjectDoneResponse, hlp.RPC_RETURN_TYPES]:

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
        clean_up_after_focus(obj_id)
        return rpc.FocusObjectDoneResponse(messages=["Focusing cancelled."])

    robot_id, end_effector = FOCUS_OBJECT_ROBOT[obj_id]

    robot_inst = SCENE_OBJECT_INSTANCES[robot_id]

    assert isinstance(robot_inst, Robot)
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
        obj.pose = await hlp.run_in_executor(robot_inst.focus, mfa)
    except NotImplementedError:  # TODO it is too late to realize it here!
        clean_up_after_focus(obj_id)
        return False, "The robot does not support focussing."

    await logger.info(f"Done focusing for {obj_id}.")

    clean_up_after_focus(obj_id)

    asyncio.ensure_future(notify_scene_change_to_others())
    return None


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
    resp = cast(rpc.ProjectStateResponse, await manager_request(rpc.ProjectStateRequest(id=uuid.uuid4().int)))  # type: ignore

    await asyncio.wait([websocket.send(ProjectStateEvent(data=resp.data.project).to_json())])
    if resp.data.action:
        await asyncio.wait([websocket.send(ActionStateEvent(data=resp.data.action).to_json())])
    if resp.data.action_args:
        await asyncio.wait([websocket.send(CurrentActionEvent(data=resp.data.action_args).to_json())])


async def unregister(websocket) -> None:
    await logger.info("Unregistering ui")  # TODO print out some identifier
    INTERFACES.remove(websocket)

async def add_collision(obj: Generic) -> None:

    if not obj.collision_model:
        return

    rs = find_robot_service()
    if rs:
        await hlp.run_in_executor(rs.add_collision(obj))


async def add_object_to_scene(obj: SceneObject, add_to_scene=True) -> Tuple[bool, str]:
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

    if obj_meta.needs_services:
        return False, "Service(s)-based object."

    if obj_meta.abstract:
        return False, "Cannot instantiate abstract type."

    if obj.id in SCENE_OBJECT_INSTANCES:
        return False, "Object with that id already exists."

    if not obj.id.isidentifier() or keyword.iskeyword(obj.id) and obj.id != hlp.camel_case_to_snake_case(obj.id):
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

        obj_inst = cls(obj.id, obj.pose, coll_model)
        SCENE_OBJECT_INSTANCES[obj.id] = obj_inst

        if add_to_scene:
            SCENE.objects.append(obj)

        await add_collision(obj_inst)

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
        for obj_inst in cls.from_services(*args):

            assert isinstance(obj_inst, Generic)

            if obj_inst.id in SCENE_OBJECT_INSTANCES:
                await logger.warning(f"Object id {obj_inst.id} already in scene.")
                continue

            SCENE_OBJECT_INSTANCES[obj_inst.id] = obj_inst
            SCENE.objects.append(obj_inst.scene_object())

            if obj_meta.object_model:
                obj_inst.collision_model = obj_meta.object_model.model()
                await add_collision(obj_inst)

    except Arcor2Exception as e:
        await logger.error(e)
        return False, "System error"

    return True, "ok"


@scene_needed
@no_project
async def add_object_to_scene_cb(req: rpc.AddObjectToSceneRequest) -> Union[rpc.AddObjectToSceneResponse, hlp.RPC_RETURN_TYPES]:

    obj = req.args
    res, msg = await add_object_to_scene(obj)

    if not res:
        return res, msg

    asyncio.ensure_future(notify_scene_change_to_others())
    return None


@scene_needed
@no_project
async def auto_add_object_to_scene_cb(req: rpc.AutoAddObjectToSceneRequest) -> Union[rpc.AutoAddObjectToSceneResponse,
                                                                                 hlp.RPC_RETURN_TYPES]:

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
        for obj_inst in SCENE_OBJECT_INSTANCES.values():
            if obj_inst.collision_model:
                await hlp.run_in_executor(srv_inst.add_collision, obj_inst)

    return True, "ok"


@scene_needed
@no_project
async def add_service_to_scene_cb(req: rpc.AddServiceToSceneRequest) -> Union[rpc.AddServiceToSceneResponse, hlp.RPC_RETURN_TYPES]:

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
async def scene_object_usage_request_cb(req: rpc.SceneObjectUsageRequest) -> Union[rpc.SceneObjectUsageResponse,
                                                                               hlp.RPC_RETURN_TYPES]:
    """
    Works for both services and objects.
    :param req:
    :return:
    """

    assert SCENE

    if not (any(obj.id == req.args.id for obj in SCENE.objects) or
            any(srv.type == req.args.id for srv in SCENE.services)):
        return False, "Unknown ID."

    resp = rpc.SceneObjectUsageResponse()

    async for project in projects_using_object(SCENE.id, req.args.id):
        resp.data.add(project.id)

    return resp


@scene_needed
@no_project
async def remove_from_scene_cb(req: rpc.RemoveFromSceneRequest) -> Union[rpc.RemoveFromSceneResponse, hlp.RPC_RETURN_TYPES]:

    assert SCENE

    if req.args.id in SCENE_OBJECT_INSTANCES:

        SCENE.objects = [obj for obj in SCENE.objects if obj.id != req.args.id]
        obj_inst = SCENE_OBJECT_INSTANCES[req.args.id]

        if obj_inst.collision_model:
            rs = find_robot_service()
            if rs:
                await hlp.run_in_executor(rs.remove_collision, obj_inst)

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
                actions_using_invalid_param: Set[str] = \
                    {act.id for act in ap.actions for param in act.parameters
                     if param.type == ActionParameterTypeEnum.ACTION_POINT and param.value.startswith(obj_id)}

                ap.actions = [act for act in ap.actions if act.id not in actions_using_invalid_param]

                # get IDs of remaining actions
                action_ids.update({act.id for act in ap.actions})

        valid_ids: Set[str] = action_ids | ActionIOEnum.set()

        # remove invalid inputs/outputs
        for obj in project.objects:
            for ap in obj.action_points:
                for act in ap.actions:
                    act.inputs = [input for input in act.inputs if input.default in valid_ids]
                    act.outputs = [output for output in act.outputs if output.default in valid_ids]

        await storage.update_project(project)
        updated_project_ids.add(project.id)
        # TODO what to do with project sources?

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

        # TODO don't allow change of pose for service-based objects
        for obj in event.data.objects:
            if obj.id not in SCENE_OBJECT_INSTANCES:
                await notify_scene(ui)
                await logger.warning("Ignoring scene changes: object added.")
                return
    else:
        await logger.info("Clearing the scene.")
        SCENE_OBJECT_INSTANCES.clear()  # TODO delete collision objects
        SERVICES_INSTANCES.clear()

    SCENE = event.data
    await notify_scene_change_to_others(ui)


async def project_change(ui, event: ProjectChangedEvent) -> None:

    global PROJECT

    PROJECT = event.data

    await notify_project_change_to_others(ui)


RPC_DICT: hlp.RPC_DICT_TYPE = {
    rpc.GetObjectTypesRequest: get_object_types_cb,
    rpc.GetActionsRequest: get_object_actions_cb,
    rpc.SaveProjectRequest: save_project_cb,
    rpc.SaveSceneRequest: save_scene_cb,
    rpc.UpdateActionPointPoseRequest: update_action_point_cb,
    rpc.UpdateActionObjectPoseRequest: update_action_object_cb,
    rpc.OpenProjectRequest: open_project_cb,
    rpc.ListProjectsRequest: list_projects_cb,
    rpc.ListScenesRequest: list_scenes_cb,
    rpc.NewObjectTypeRequest: new_object_type_cb,
    rpc.ListMeshesRequest: list_meshes_cb,
    rpc.FocusObjectRequest: focus_object_cb,
    rpc.FocusObjectStartRequest: focus_object_start_cb,
    rpc.FocusObjectDoneRequest: focus_object_done_cb,
    rpc.GetServicesRequest: get_services_cb,
    rpc.AddObjectToSceneRequest: add_object_to_scene_cb,
    rpc.AutoAddObjectToSceneRequest: auto_add_object_to_scene_cb,
    rpc.AddServiceToSceneRequest: add_service_to_scene_cb,
    rpc.RemoveFromSceneRequest: remove_from_scene_cb,
    rpc.SceneObjectUsageRequest: scene_object_usage_request_cb,
    rpc.OpenSceneRequest: open_scene_cb
}

# add Project Manager RPC API
for k, v in MANAGER_RPC_DICT.items():
    RPC_DICT[k] = manager_request


EVENT_DICT: hlp.EVENT_DICT_TYPE = {
    SceneChangedEvent: scene_change,
    ProjectChangedEvent: project_change
}


def main():

    assert sys.version_info >= (3, 6)

    loop = asyncio.get_event_loop()
    loop.set_debug(enabled=True)

    bound_handler = functools.partial(hlp.server, logger=logger, register=register, unregister=unregister,
                                      rpc_dict=RPC_DICT, event_dict=EVENT_DICT)

    asyncio.wait([asyncio.gather(websockets.serve(bound_handler, '0.0.0.0', 6789), project_manager_client(),
                        _initialize_server())])
    loop.run_forever()


if __name__ == "__main__":
    main()
