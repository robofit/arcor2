#!/usr/bin/env python3
# -*- coding: utf-8 -*-


import asyncio
import json
import functools
import sys
from typing import Dict, Set, Union, get_type_hints
import inspect
import copy

import websockets  # type: ignore
from aiologger import Logger  # type: ignore
import motor.motor_asyncio  # type: ignore
from undecorated import undecorated  # type: ignore
from dataclasses_jsonschema import ValidationError

from arcor2.source.logic import program_src
from arcor2.source.object_types import object_type_info, get_object_actions
from arcor2.source.utils import derived_resources_class
from arcor2.source import SourceException
from arcor2.exceptions import Arcor2Exception
from arcor2.nodes.manager import RPC_DICT as MANAGER_RPC_DICT
from arcor2.helpers import response, rpc, server
from arcor2.data import Scene, Project, ObjectType, ObjectAction, ObjectActionArgs, ObjectActions


# TODO validation of scene/project -> in thread pool executor (CPU intensive)
# TODO notify RPC requests to other interfaces to let them know what happened?
from arcor2.helpers import built_in_types, built_in_types_names

logger = Logger.with_default_handlers(name='arcor2-server')

mongo = motor.motor_asyncio.AsyncIOMotorClient()

SCENE: Union[Scene, None] = None
PROJECT: Union[Project, None] = None
INTERFACES: Set = set()

JSON_SCHEMAS = {"scene": Scene.json_schema(),
                "project": Project.json_schema()}

MANAGER_RPC_REQUEST_QUEUE: asyncio.Queue = asyncio.Queue()
MANAGER_RPC_RESPONSE_QUEUE: asyncio.Queue = asyncio.Queue()
MANAGER_RPC_REQ_ID: int = 0

ObjectActionsDict = Dict[str, ObjectActions]

# TODO watch for changes (just clear on change)
OBJECT_TYPES: Dict[str, ObjectType] = {}
OBJECT_ACTIONS: ObjectActionsDict = {}


async def handle_manager_incoming_messages(manager_client):

    try:

        async for message in manager_client:

            msg = json.loads(message)
            await logger.info(f"Message from manager: {msg}")

            if "event" in msg:
                await asyncio.wait([intf.send(json.dumps(msg)) for intf in INTERFACES])
            elif "response" in msg:
                await MANAGER_RPC_RESPONSE_QUEUE.put(msg)

    except websockets.exceptions.ConnectionClosed:
        await logger.error("Connection to manager closed.")
        # TODO try to open it again and refuse requests meanwhile


async def project_manager_client():

    while True:

        await logger.info("Attempting connection to manager...")

        # TODO if manager does not run initially, this won't connect even if the manager gets started afterwards
        async with websockets.connect("ws://localhost:6790") as manager_client:

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
                    await manager_client.send(json.dumps(msg))
                except websockets.exceptions.ConnectionClosed:
                    await MANAGER_RPC_REQUEST_QUEUE.put(msg)
                    break


def scene_event() -> str:

    data: Dict = {}

    if SCENE is not None:
        data = SCENE.to_dict()

    return json.dumps({"event": "sceneChanged", "data": data})  # TODO use encoder?


def project_event() -> str:

    data: Dict = {}

    if PROJECT is not None:
        data = PROJECT.to_dict()

    return json.dumps({"event": "projectChanged", "data": data})  # TODO use encoder?


async def notify_scene_change_to_others(interface=None) -> None:
    if len(INTERFACES) > 1:
        message = scene_event()
        await asyncio.wait([intf.send(message) for intf in INTERFACES if intf != interface])


async def notify_project_change_to_others(interface=None) -> None:
    if len(INTERFACES) > 1:
        message = project_event()
        await asyncio.wait([intf.send(message) for intf in INTERFACES if intf != interface])


async def notify_scene(interface) -> None:
    message = scene_event()
    await asyncio.wait([interface.send(message)])


async def notify_project(interface) -> None:
    message = project_event()
    await asyncio.wait([interface.send(message)])


class DataError(Arcor2Exception):
    pass


def obj_description_from_base(data: Dict[str, ObjectType], obj_type: ObjectType) -> str:

    try:
        obj = data[obj_type.base]
    except KeyError:
        raise DataError(f"Unknown object type: {obj_type}.")

    if obj.description:
        return obj.description

    if not obj.base:
        return ""

    return obj_description_from_base(data, data[obj.base])


async def _get_object_types():  # TODO watch db for changes and call this + notify UI in case of something changed

    global OBJECT_TYPES

    object_types: Dict[str, ObjectType] = {}

    # built-in object types
    for type_name, type_def in built_in_types():

        obj = ObjectType(type_name, type_def.__DESCRIPTION__, True)

        bases = inspect.getmro(type_def)

        assert 1 < len(bases) < 4

        if len(bases) == 3:
            obj.base = bases[1].__name__

        object_types[type_name] = obj

    # db-stored (user-created) types
    cursor = mongo.arcor2.object_types.find({})
    for obj in await cursor.to_list(None):
        try:
            object_types[obj["id"]] = object_type_info(obj["source"])
        except KeyError:
            continue

    to_delete = set()

    for obj_type, obj in object_types.items():
        if not obj.description:
            try:
                obj.description = obj_description_from_base(object_types, obj)
            except DataError as e:
                await logger.error(f"Failed to get info from base for {obj_type}, error: '{e}'.")
                to_delete.add(obj_type)

    for obj_type in to_delete:
        del object_types[obj_type]

    OBJECT_TYPES = object_types

    await _get_object_actions()


@rpc(logger)
async def get_object_types_cb(req: str, ui, args: Dict) -> Dict:

    msg = response(req, data=list(OBJECT_TYPES.values()))
    return msg


@rpc(logger)
async def save_scene_cb(req, ui, args) -> Dict:

    if SCENE is None or not SCENE.id:
        return response(req, False, ["Scene not opened or invalid."])

    msg = response(req)

    db = mongo.arcor2

    old_scene_data = await db.scenes.find_one({"id": SCENE.id})
    if old_scene_data:
        old_scene = Scene.from_dict(old_scene_data)
        await db.scenes.replace_one({'id': old_scene.id}, SCENE.to_dict())
        await logger.debug("scene updated")
    else:
        await db.scenes.insert_one(SCENE.to_dict())
        await logger.debug("scene created")

    return msg


@rpc(logger)
async def save_project_cb(req, ui, args) -> Dict:

    if PROJECT is None or not PROJECT.id:
        return response(req, False, ["Project not opened or invalid."])

    if SCENE is None or not SCENE.id:
        return response(req, False, ["Scene not opened or invalid."])

    action_names = []

    try:
        for obj in PROJECT.objects:
            for aps in obj.action_points:
                for act in aps.actions:
                    action_names.append(act.id)
    except KeyError as e:
        await logger.error(f"Project data invalid: {e}")
        return response(req, False, ["Project data invalid!", str(e)])

    # TODO store sources separately?
    project_db = PROJECT.to_dict()
    project_db["sources"] = {}
    project_db["sources"]["resources"] = derived_resources_class(PROJECT.id, action_names)
    project_db["sources"]["script"] = program_src(PROJECT, SCENE, built_in_types_names())

    db = mongo.arcor2
    # TODO validate project here or in DB?

    old_project = await db.projects.find_one({"id": project_db["id"]})  # TODO how to get only id?
    if old_project:
        await db.projects.replace_one({'id': old_project["id"]}, project_db)
        await logger.debug("project updated")
    else:
        await db.projects.insert_one(project_db)
        await logger.debug("project created")

    return response(req)


async def _get_object_actions():

    global OBJECT_ACTIONS

    object_actions: ObjectActionsDict = {}

    # built-in object types
    for type_name, type_def in built_in_types():

        if type_name not in OBJECT_TYPES:
            continue

        # ...inspect.ismethod does not work on un-initialized classes
        for method in inspect.getmembers(type_def, predicate=inspect.isfunction):

            # TODO check also if the method has 'action' decorator (ast needed)
            if not hasattr(method[1], "__action__"):
                continue

            meta = method[1].__action__

            data = ObjectAction(name=method[0], meta=meta)

            """
            Methods supposed to be actions have @action decorator, which has to be stripped away in order to get
            method's arguments / type hints.
            """
            undecorated_method = undecorated(method[1])

            for name, ttype in get_type_hints(undecorated_method).items():

                try:
                    if name == "return":
                        data.returns = ttype.__name__
                        continue

                    data.action_args.append(ObjectActionArgs(name=name, type=ttype.__name__))

                except AttributeError:
                    print(f"Skipping {ttype}")  # TODO make a fix for Union

            if type_name not in object_actions:
                object_actions[type_name] = []
            object_actions[type_name].append(data)

    for obj_type, obj in OBJECT_TYPES.items():

        if obj.built_in:  # built-in types are already there
            continue

        # db-stored (user-created) object types
        db = mongo.arcor2
        obj_db = await db.object_types.find_one({"id": obj_type})
        try:
            # TODO weird - store obj type source separately!
            object_actions[obj_type] = get_object_actions(obj_db["source"])
        except SourceException as e:
            await logger.error(e)

    # add actions from ancestors
    for obj_type in OBJECT_TYPES.keys():
        add_ancestor_actions(obj_type, object_actions)

    OBJECT_ACTIONS = object_actions


def add_ancestor_actions(obj_type: str, object_actions: ObjectActionsDict):

    base_name = OBJECT_TYPES[obj_type].base

    if not base_name:
        return

    if OBJECT_TYPES[base_name].base:
        add_ancestor_actions(base_name, object_actions)

    # do not add action from base if it is overridden in child
    for base_action in object_actions[base_name]:
        for obj_action in object_actions[obj_type]:
            if base_action.name == obj_action.name:

                # built-in object has no "origins" yet
                if not obj_action.origins:
                    obj_action.origins = base_name
                break
        else:
            action = copy.deepcopy(base_action)
            if not action.origins:
                action.origins = base_name
            object_actions[obj_type].append(action)


@rpc(logger)
async def get_object_actions_cb(req, ui, args) -> Union[Dict, None]:

    try:
        obj_type = args["type"]
    except KeyError:
        return None

    try:
        return response(req, data=OBJECT_ACTIONS[obj_type])
    except KeyError:
        return response(req, False, [f'Unknown object type: {obj_type}.'])


@rpc(logger)
async def manager_request(req, ui, args) -> Dict:

    global MANAGER_RPC_REQ_ID

    req_id = MANAGER_RPC_REQ_ID
    msg = {"request": req, "args": args, "req_id": req_id}
    MANAGER_RPC_REQ_ID += 1

    await MANAGER_RPC_REQUEST_QUEUE.put(msg)
    # TODO process request

    # TODO better way to get correct response based on req_id?
    while True:
        resp = await MANAGER_RPC_RESPONSE_QUEUE.get()
        if resp["req_id"] == req_id:
            del resp["req_id"]
            return resp
        else:
            await MANAGER_RPC_RESPONSE_QUEUE.put(resp)


@rpc(logger)
async def get_schema_cb(req, ui, args) -> Union[Dict, None]:

    try:
        which = args["type"]
    except KeyError:
        return None

    if which not in JSON_SCHEMAS:
        return response(ui, False, ["Unknown type."])

    return response(req, data=JSON_SCHEMAS[which])


async def register(websocket) -> None:
    await logger.info("Registering new ui")
    INTERFACES.add(websocket)
    await notify_scene(websocket)
    await notify_project(websocket)


async def unregister(websocket) -> None:
    await logger.info("Unregistering ui")  # TODO print out some identifier
    INTERFACES.remove(websocket)


async def scene_change(ui, scene) -> None:

    global SCENE

    try:
        SCENE = Scene.from_dict(scene)
    except ValidationError as e:
        await logger.error(e)
        return

    await notify_scene_change_to_others(ui)


async def project_change(ui, project) -> None:

    global PROJECT

    try:
        PROJECT = Project.from_dict(project)
    except ValidationError as e:
        await logger.error(e)
        return

    await notify_project_change_to_others(ui)


RPC_DICT: Dict = {'getObjectTypes': get_object_types_cb,
                  'getObjectActions': get_object_actions_cb,
                  'saveProject': save_project_cb,
                  'saveScene': save_scene_cb,
                  'getSchema': get_schema_cb}

# add Project Manager RPC API
for k, v in MANAGER_RPC_DICT.items():
    RPC_DICT[k] = manager_request

EVENT_DICT: Dict = {'sceneChanged': scene_change,
                    'projectChanged': project_change}


async def multiple_tasks():

    bound_handler = functools.partial(server, logger=logger, register=register, unregister=unregister,
                                      rpc_dict=RPC_DICT, event_dict=EVENT_DICT)
    input_coroutines = [websockets.serve(bound_handler, '0.0.0.0', 6789), project_manager_client(),
                        _get_object_types()]
    res = await asyncio.gather(*input_coroutines, return_exceptions=True)
    return res


def main():

    assert sys.version_info >= (3, 6)

    loop = asyncio.get_event_loop()
    loop.set_debug(enabled=True)
    loop.run_until_complete(multiple_tasks())
    loop.run_forever()


if __name__ == "__main__":
    main()
