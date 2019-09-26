#!/usr/bin/env python3
# -*- coding: utf-8 -*-


import asyncio
import json
import functools
import sys
from typing import Dict, Set, Union, TYPE_CHECKING, Tuple, Optional, List, Callable, cast
from types import ModuleType
import uuid

import websockets
from websockets.server import WebSocketServerProtocol
from aiologger import Logger  # type: ignore

from arcor2.source.logic import program_src, get_logic_from_source
from arcor2.source.object_types import object_type_meta, get_object_actions, new_object_type_source
from arcor2.source.utils import derived_resources_class
from arcor2.source import SourceException
from arcor2.nodes.manager import RPC_DICT as MANAGER_RPC_DICT, PORT as MANAGER_PORT
from arcor2.helpers import server, aiologger_formatter, RPC_RETURN_TYPES, RPC_DICT_TYPE, EVENT_DICT_TYPE
from arcor2.object_types_utils import built_in_types_names, DataError, obj_description_from_base, built_in_types_meta, \
    built_in_types_actions, add_ancestor_actions, get_built_in_type
from arcor2.data.common import Scene, Project, ProjectSources, Pose, Position
from arcor2.data.object_type import ObjectActionsDict, ObjectTypeMetaDict, ObjectTypeMeta, ModelTypeEnum, \
    MeshFocusAction, ObjectModel
from arcor2.data.rpc import GetObjectActionsRequest, GetObjectTypesResponse, GetObjectTypesRequest, \
    GetObjectActionsResponse, NewObjectTypeRequest, NewObjectTypeResponse, ListMeshesRequest, ListMeshesResponse, \
    Request, Response, SaveSceneRequest, SaveSceneResponse, SaveProjectRequest, SaveProjectResponse, \
    OpenProjectRequest, OpenProjectResponse, UpdateActionPointPoseRequest, UpdateActionPointPoseResponse,\
    UpdateActionObjectPoseRequest, ListProjectsRequest, ListProjectsResponse, ListScenesRequest, ListScenesResponse,\
    FocusObjectStartRequest, FocusObjectStartResponse, FocusObjectRequest, FocusObjectResponse, \
    FocusObjectDoneRequest, FocusObjectDoneResponse, ProjectStateRequest, ProjectStateResponse
from arcor2.data.events import ProjectChangedEvent, SceneChangedEvent, Event, ObjectTypesChangedEvent, \
    ProjectStateEvent, ActionStateEvent, CurrentActionEvent
from arcor2.data.helpers import RPC_MAPPING
from arcor2.persistent_storage import AioPersistentStorage
from arcor2.object_types import Generic, Robot
from arcor2.project_utils import get_action_point
from arcor2.scene_utils import get_scene_object
from arcor2.exceptions import ActionPointNotFound, SceneObjectNotFound, Arcor2Exception

if TYPE_CHECKING:
    ReqQueue = asyncio.Queue[Request]
    RespQueue = asyncio.Queue[Response]
else:
    ReqQueue = asyncio.Queue
    RespQueue = asyncio.Queue


logger = Logger.with_default_handlers(name='server', formatter=aiologger_formatter())

SCENE: Union[Scene, None] = None
PROJECT: Union[Project, None] = None
SCENE_OBJECT_INSTANCES: Dict[str, Generic] = {}

INTERFACES: Set[WebSocketServerProtocol] = set()

MANAGER_RPC_REQUEST_QUEUE: ReqQueue = ReqQueue()
MANAGER_RPC_RESPONSES: Dict[int, RespQueue] = {}

# TODO watch for changes (just clear on change)
OBJECT_TYPES: ObjectTypeMetaDict = {}
OBJECT_ACTIONS: ObjectActionsDict = {}

FOCUS_OBJECT: Dict[str, Dict[int, Pose]] = {}  # object_id / idx, pose
FOCUS_OBJECT_ROBOT: Dict[str, Tuple[str, str]] = {}  # object_id / robot, end_effector

STORAGE_CLIENT = AioPersistentStorage()


class RobotPoseException(Arcor2Exception):
    pass


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

    await _get_object_types()
    await _get_object_actions()
    await _check_manager()


async def _get_object_types() -> None:

    # TODO watch db for changes and call this + notify UI in case of something changed

    global OBJECT_TYPES

    object_types: Dict[str, ObjectTypeMeta] = built_in_types_meta()

    obj_ids = await STORAGE_CLIENT.get_object_type_ids()

    for obj_id in obj_ids.items:
        obj = await STORAGE_CLIENT.get_object_type(obj_id.id)
        try:
            object_types[obj.id] = object_type_meta(obj.source)
        except SourceException as e:
            await logger.error(f"Ignoring object type {obj.id}: {e}")
            continue

        if obj.model:
            model = await STORAGE_CLIENT.get_model(obj.model.id, obj.model.type)
            kwargs = {model.type().value.lower(): model}
            object_types[obj.id].object_model = ObjectModel(model.type(), **kwargs)  # type: ignore

    # if description is missing, try to get it from ancestor(s), or forget the object type
    to_delete: Set[str] = set()

    for obj_type, obj_meta in object_types.items():
        if not obj_meta.description:
            try:
                obj_meta.description = obj_description_from_base(object_types, obj_meta)
            except DataError as e:
                await logger.error(f"Failed to get info from base for {obj_type}, error: '{e}'.")
                to_delete.add(obj_type)

    for obj_type in to_delete:
        del object_types[obj_type]

    OBJECT_TYPES = object_types


async def get_object_types_cb(req: GetObjectTypesRequest) -> GetObjectTypesResponse:
    return GetObjectTypesResponse(data=list(OBJECT_TYPES.values()))


async def save_scene_cb(req: SaveSceneRequest) -> Union[SaveSceneResponse, RPC_RETURN_TYPES]:

    if SCENE is None or not SCENE.id:
        return False, "Scene not opened or invalid."

    await STORAGE_CLIENT.update_scene(SCENE)
    return None


async def save_project_cb(req: SaveProjectRequest) -> Union[SaveProjectResponse, RPC_RETURN_TYPES]:

    if PROJECT is None or not PROJECT.id:
        return False, "Project not opened or invalid."

    if SCENE is None or not SCENE.id:
        return False, "Scene not opened or invalid."

    action_names = []

    for obj in PROJECT.objects:
        for aps in obj.action_points:
            for act in aps.actions:
                action_names.append(act.id)

    msgs: List[str] = []
    project_sources = None

    try:
        project_sources = ProjectSources(id=PROJECT.id,
                                         resources=derived_resources_class(PROJECT.id, action_names),
                                         script=program_src(PROJECT, SCENE, built_in_types_names()))
    except SourceException as e:
        await logger.error(e)
        msgs.append("Failed to generate project sources.")

    await STORAGE_CLIENT.update_project(PROJECT)
    if project_sources:
        await STORAGE_CLIENT.update_project_sources(project_sources)

    return SaveProjectResponse(messages=msgs)


async def open_project(project_id: str) -> bool:

    global PROJECT
    global SCENE

    PROJECT = await STORAGE_CLIENT.get_project(project_id)
    SCENE = await STORAGE_CLIENT.get_scene(PROJECT.scene_id)

    project_sources = await STORAGE_CLIENT.get_project_sources(PROJECT.id)

    load_logic_failed = False

    try:
        get_logic_from_source(project_sources.script, PROJECT)
    except SourceException as e:
        load_logic_failed = True
        await logger.error(e)

    await update_scene_instances()
    await notify_project_change_to_others()
    await notify_scene_change_to_others()

    return not load_logic_failed


async def open_project_cb(req: OpenProjectRequest) -> Union[OpenProjectResponse, RPC_RETURN_TYPES]:

    logic_loaded = await open_project(req.args.id)

    if not logic_loaded:
        return True, "Failed to load logic from source."

    return None


async def _get_object_actions() -> None:

    global OBJECT_ACTIONS

    object_actions: ObjectActionsDict = built_in_types_actions()

    for obj_type, obj in OBJECT_TYPES.items():

        if obj.built_in:  # built-in types are already there
            continue

        # db-stored (user-created) object types
        obj_db = await STORAGE_CLIENT.get_object_type(obj_type)
        try:
            object_actions[obj_type] = get_object_actions(obj_db.source)
        except SourceException as e:
            await logger.error(e)

    # add actions from ancestors
    for obj_type in OBJECT_TYPES.keys():
        add_ancestor_actions(obj_type, object_actions, OBJECT_TYPES)

    OBJECT_ACTIONS = object_actions

    await notify(ObjectTypesChangedEvent(data=list(object_actions.keys())))


async def _check_manager() -> None:

    # TODO avoid cast
    resp = cast(ProjectStateResponse, await manager_request(ProjectStateRequest(id=uuid.uuid4().int)))

    if resp.data.id is not None and (PROJECT is None or PROJECT.id != resp.data.id):
        await open_project(resp.data.id)


async def get_object_actions_cb(req: GetObjectActionsRequest) -> Union[GetObjectActionsResponse, RPC_RETURN_TYPES]:

    try:
        return GetObjectActionsResponse(data=OBJECT_ACTIONS[req.args.type])
    except KeyError:
        return False, f"Unknown object type: '{req.args.type}'."


async def manager_request(req: Request) -> Response:

    assert req.id not in MANAGER_RPC_RESPONSES

    MANAGER_RPC_RESPONSES[req.id] = RespQueue(maxsize=1)
    await MANAGER_RPC_REQUEST_QUEUE.put(req)

    resp = await MANAGER_RPC_RESPONSES[req.id].get()
    del MANAGER_RPC_RESPONSES[req.id]
    return resp


async def get_end_effector_pose(robot_id: str, end_effector: str) -> Pose:

    try:
        robot = SCENE_OBJECT_INSTANCES[robot_id]
    except KeyError:
        raise RobotPoseException("Unknown robot.")

    if not isinstance(robot, Robot):
        raise RobotPoseException(f"Object {robot_id} is not instance of Robot!")

    # TODO validate end-effector

    # TODO transform pose from robot somehow
    try:
        return await asyncio.get_event_loop().run_in_executor(None, robot.get_pose, end_effector)
    except NotImplementedError:
        raise RobotPoseException("The robot does not support getting pose.")


async def update_action_point_cb(req: UpdateActionPointPoseRequest) -> Union[UpdateActionPointPoseResponse,
                                                                             RPC_RETURN_TYPES]:

    if not (SCENE and PROJECT and SCENE.id and PROJECT.id):  # TODO use decorator for this
        return False, "Scene/project has to be loaded first."

    try:
        ap = get_action_point(PROJECT, req.args.id)
    except ActionPointNotFound:
        return False, "Invalid action point."

    try:
        ap.pose = await get_end_effector_pose(req.args.robot.id, req.args.robot.end_effector)
    except RobotPoseException as e:
        return False, str(e)

    await notify_project_change_to_others()
    return None


async def update_action_object_cb(req: UpdateActionObjectPoseRequest) -> Union[UpdateActionObjectPoseRequest,
                                                                               RPC_RETURN_TYPES]:

    if not (SCENE and SCENE.id):
        return False, "Scene has to be loaded first."

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

    await notify_scene_change_to_others()
    return None


async def list_projects_cb(req: ListProjectsRequest) -> Union[ListProjectsResponse, RPC_RETURN_TYPES]:

    projects = await STORAGE_CLIENT.get_projects()
    return ListProjectsResponse(data=projects.items)


async def list_scenes_cb(req: ListScenesRequest) -> Union[ListScenesResponse, RPC_RETURN_TYPES]:

    scenes = await STORAGE_CLIENT.get_scenes()
    return ListScenesResponse(data=scenes.items)


async def list_meshes_cb(req: ListMeshesRequest) -> Union[ListMeshesResponse, RPC_RETURN_TYPES]:
    return ListMeshesResponse(data=await STORAGE_CLIENT.get_meshes())


async def new_object_type_cb(req: NewObjectTypeRequest) -> Union[NewObjectTypeResponse, RPC_RETURN_TYPES]:

    meta = req.args

    if meta.type in OBJECT_TYPES:
        return False, "Object type already exists."

    if meta.base not in OBJECT_TYPES:
        return False, "Unknown base object type."

    obj = meta.to_object_type()
    obj.source = new_object_type_source(OBJECT_TYPES[meta.base], meta)

    if meta.object_model and meta.object_model.type != ModelTypeEnum.MESH:
        assert meta.type == meta.object_model.model().id
        await STORAGE_CLIENT.put_model(meta.object_model.model())

    # TODO check whether mesh id exists - if so, then use existing mesh, if not, upload a new one
    if meta.object_model and meta.object_model.type == ModelTypeEnum.MESH:
        # ...get whole mesh (focus_points) based on mesh id
        assert meta.object_model.mesh
        meta.object_model.mesh = await STORAGE_CLIENT.get_mesh(meta.object_model.mesh.id)

    await STORAGE_CLIENT.update_object_type(obj)

    OBJECT_TYPES[meta.type] = meta
    OBJECT_ACTIONS[meta.type] = get_object_actions(obj.source)
    add_ancestor_actions(meta.type, OBJECT_ACTIONS, OBJECT_TYPES)

    await notify(ObjectTypesChangedEvent(data=[meta.type]))
    return None


async def focus_object_start_cb(req: FocusObjectStartRequest) -> Union[FocusObjectStartResponse, RPC_RETURN_TYPES]:

    global FOCUS_OBJECT
    global FOCUS_OBJECT_ROBOT

    # TODO decorator to check if scene is loaded
    if not SCENE or not SCENE.id:
        return False, "Scene not loaded."

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


async def focus_object_cb(req: FocusObjectRequest) -> Union[FocusObjectResponse, RPC_RETURN_TYPES]:

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

    r = FocusObjectResponse()
    r.data.finished_indexes = list(FOCUS_OBJECT[obj_id].keys())
    return r


async def focus_object_done_cb(req: FocusObjectDoneRequest) -> Union[FocusObjectDoneResponse, RPC_RETURN_TYPES]:

    global FOCUS_OBJECT
    global FOCUS_OBJECT_ROBOT

    # TODO decorator to check if scene is loaded etc.

    obj_id = req.args.id

    if obj_id not in FOCUS_OBJECT:
        return False, "focusObjectStart/focusObject has to be called first."

    obj_type = OBJECT_TYPES[get_obj_type_name(obj_id)]

    assert obj_type.object_model and obj_type.object_model.mesh

    focus_points = obj_type.object_model.mesh.focus_points

    assert focus_points

    if len(FOCUS_OBJECT[obj_id]) < len(focus_points):
        clean_up_after_focus(obj_id)
        return FocusObjectDoneResponse(messages=["Focusing cancelled."])

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
        obj.pose = await asyncio.get_event_loop().run_in_executor(None, robot_inst.focus, mfa)
    except NotImplementedError:  # TODO it is too late to realize it here!
        clean_up_after_focus(obj_id)
        return False, "The robot does not support focussing."

    await logger.info(f"Done focusing for {obj_id}.")

    clean_up_after_focus(obj_id)

    await notify_scene_change_to_others()
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
    resp = cast(ProjectStateResponse, await manager_request(ProjectStateRequest(id=uuid.uuid4().int)))

    await asyncio.wait([websocket.send(ProjectStateEvent(data=resp.data.project).to_json())])
    if resp.data.action:
        await asyncio.wait([websocket.send(ActionStateEvent(data=resp.data.action).to_json())])
    if resp.data.action_args:
        await asyncio.wait([websocket.send(CurrentActionEvent(data=resp.data.action_args).to_json())])


async def unregister(websocket) -> None:
    await logger.info("Unregistering ui")  # TODO print out some identifier
    INTERFACES.remove(websocket)


async def update_scene_instances() -> None:

    scene_obj_ids: Set[str] = set()

    assert SCENE

    for obj in SCENE.objects:

        scene_obj_ids.add(obj.id)

        if obj.id not in SCENE_OBJECT_INSTANCES:

            await logger.debug(f"Creating instance {obj.id} ({obj.type}).")

            if obj.type in built_in_types_names():  # TODO is it ok to create instances of built-in object types?
                cls = get_built_in_type(obj.type)
            else:
                obj_type = await STORAGE_CLIENT.get_object_type(obj.type)
                mod = ModuleType('temp_module')
                exec(obj_type.source, mod.__dict__)
                cls = getattr(mod, obj.type)

            SCENE_OBJECT_INSTANCES[obj.id] = cls()  # TODO name, pose, etc.

    # delete instances which were deleted from the scene
    for obj_id in set(SCENE_OBJECT_INSTANCES.keys()) - scene_obj_ids:
        await logger.debug(f"Deleting {obj_id} instance.")
        del SCENE_OBJECT_INSTANCES[obj_id]


async def scene_change(ui, event: SceneChangedEvent) -> None:

    global SCENE

    SCENE = event.data

    await update_scene_instances()
    await notify_scene_change_to_others(ui)


async def project_change(ui, event: ProjectChangedEvent) -> None:

    global PROJECT

    PROJECT = event.data

    await notify_project_change_to_others(ui)


RPC_DICT: RPC_DICT_TYPE = {
    GetObjectTypesRequest: get_object_types_cb,
    GetObjectActionsRequest: get_object_actions_cb,
    SaveProjectRequest: save_project_cb,
    SaveSceneRequest: save_scene_cb,
    UpdateActionPointPoseRequest: update_action_point_cb,
    UpdateActionObjectPoseRequest: update_action_object_cb,
    OpenProjectRequest: open_project_cb,
    ListProjectsRequest: list_projects_cb,
    ListScenesRequest: list_scenes_cb,
    NewObjectTypeRequest: new_object_type_cb,
    ListMeshesRequest: list_meshes_cb,
    FocusObjectRequest: focus_object_cb,
    FocusObjectStartRequest: focus_object_start_cb,
    FocusObjectDoneRequest: focus_object_done_cb
}

# add Project Manager RPC API
for k, v in MANAGER_RPC_DICT.items():
    RPC_DICT[k] = manager_request


EVENT_DICT: EVENT_DICT_TYPE = {
    SceneChangedEvent: scene_change,
    ProjectChangedEvent: project_change
}


async def multiple_tasks():

    bound_handler = functools.partial(server, logger=logger, register=register, unregister=unregister,
                                      rpc_dict=RPC_DICT, event_dict=EVENT_DICT)
    input_coroutines = [websockets.serve(bound_handler, '0.0.0.0', 6789), project_manager_client(),
                        _initialize_server()]
    res = await asyncio.gather(*input_coroutines)
    return res


def main():

    assert sys.version_info >= (3, 6)

    loop = asyncio.get_event_loop()
    loop.set_debug(enabled=True)
    loop.run_until_complete(multiple_tasks())
    loop.run_forever()


if __name__ == "__main__":
    main()
