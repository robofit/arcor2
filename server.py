#!/usr/bin/env python3
# -*- coding: utf-8 -*-


import asyncio
import json
import websockets  # type: ignore
import functools
import sys
from typing import Dict, Set, List
import inspect
from arcor2 import generate_source
from typing import get_type_hints
from aiologger import Logger  # type: ignore
import motor.motor_asyncio  # type: ignore
from arcor2.manager import RPC_DICT as MANAGER_RPC_DICT
from arcor2.helpers import response, rpc, server, validate_event, read_schema
from undecorated import undecorated
import fastjsonschema


# TODO validation of scene/project -> in thread pool executor (CPU intensive)
# TODO notify RPC requests to other interfaces to let them know what happened?
from helpers import built_in_types, built_in_types_names

logger = Logger.with_default_handlers(name='arcor2-server')

mongo = motor.motor_asyncio.AsyncIOMotorClient()

SCENE: Dict = {}
PROJECT: Dict = {}
INTERFACES: Set = set()

MANAGER_RPC_REQUEST_QUEUE: asyncio.Queue = asyncio.Queue()
MANAGER_RPC_RESPONSE_QUEUE: asyncio.Queue = asyncio.Queue()
MANAGER_RPC_REQ_ID: int = 0

# TODO watch for changes (just clear on change)
OBJECT_TYPES: Dict[str, Dict] = {}
OBJECT_ACTIONS: Dict[str, List[Dict]] = {}


VALIDATE_SCENE = fastjsonschema.compile(read_schema("scene"))
VALIDATE_PROJECT = fastjsonschema.compile(read_schema("project"))


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
    return json.dumps({"event": "sceneChanged", "data": SCENE})


def project_event() -> str:
    return json.dumps({"event": "projectChanged", "data": PROJECT})


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


class DataError(Exception):
    pass


def obj_description_from_base(data: Dict, obj_type: str) -> str:

    try:
        obj = data[obj_type]
    except KeyError:
        raise DataError(f"Unknown object type: {obj_type}.")

    if obj["description"]:
        return obj["description"]

    if not obj["base"]:
        return ""

    return obj_description_from_base(data, obj["base"])


async def _get_object_types():  # TODO watch db for changes and call this + notify UI in case of something changed

    global OBJECT_TYPES

    object_types: Dict[str, Dict] = {}

    # built-in object types
    for type_name, type_def in built_in_types():

        d = {"description": type_def.__DESCRIPTION__, "built-in": True}

        bases = inspect.getmro(type_def)

        assert 1 < len(bases) < 4

        if len(bases) == 3:
            d["base"] = bases[1].__name__

        object_types[type_name] = d

    # db-stored (user-created) types
    cursor = mongo.arcor2.object_types.find({})
    for obj in await cursor.to_list(None):
        object_types[obj["_id"]] = generate_source.object_type_info(obj["source"])

    to_delete = set()

    for obj_type, obj in object_types.items():
        if not obj["description"]:
            try:
                obj["description"] = obj_description_from_base(object_types, obj_type)
            except DataError as e:
                await logger.error(f"Failed to get info from base for {obj_type}, error: '{e}'.")
                to_delete.add(obj_type)

    for obj_type in to_delete:
        del object_types[obj_type]

    OBJECT_TYPES = object_types

    await _get_object_actions()


@rpc(logger)
async def get_object_types(req: str, ui, args: Dict) -> Dict:

    msg = response(req)
    msg["data"] = []

    for obj_type, obj_data in OBJECT_TYPES.items():
        d = {"type": obj_type}
        d.update(obj_data)
        msg["data"].append(d)

    return msg


@rpc(logger)
async def save_scene(req, ui, args) -> Dict:

    if "_id" not in SCENE:
        return response(req, False, ["Scene not opened or invalid."])

    msg = response(req)

    db = mongo.arcor2

    old_scene = await db.scenes.find_one({"_id": SCENE["_id"]})
    if old_scene:
        await db.scenes.replace_one({'_id': old_scene["_id"]}, SCENE)
        await logger.debug("scene updated")
    else:
        await db.scenes.insert_one(SCENE)
        await logger.debug("scene created")

    return msg


@rpc(logger)
async def save_project(req, ui, args) -> Dict:

    if "_id" not in PROJECT:
        return response(req, False, ["Project not opened or invalid."])

    action_names = []

    try:
        for obj in PROJECT["objects"]:
            for aps in obj["action_points"]:
                for act in aps["actions"]:
                    action_names.append(act["id"])
    except KeyError as e:
        await logger.error(f"Project data invalid: {e}")
        return response(req, False, ["Project data invalid!", str(e)])

    project_db = PROJECT.copy()  # shallow copy is enough here
    project_db["sources"] = {}
    project_db["sources"]["resources"] = generate_source.derived_resources_class(PROJECT["_id"], action_names)
    project_db["sources"]["script"] = generate_source.SCRIPT_HEADER +\
        generate_source.program_src(PROJECT, SCENE, built_in_types_names())

    db = mongo.arcor2
    # TODO validate project here or in DB?

    old_project = await db.projects.find_one({"_id": project_db["_id"]})  # TODO how to get only id?
    if old_project:
        await db.projects.replace_one({'_id': old_project["_id"]}, project_db)
        await logger.debug("project updated")
    else:
        await db.projects.insert_one(project_db)
        await logger.debug("project created")

    return response(req)


async def _get_object_actions():

    global OBJECT_ACTIONS

    object_actions: Dict[str, List[Dict]] = {}

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

            data = {"name": method[0], "blocking": meta.blocking, "free": meta.free, "composite": False,
                    "blackbox": False,
                    "action_args": []}

            """
            Methods supposed to be actions have @action decorator, which has to be stripped away in order to get
            method's arguments / type hints.
            """
            undecorated_method = undecorated(method[1])

            for name, ttype in get_type_hints(undecorated_method).items():

                try:
                    if name == "return":
                        data["returns"] = ttype.__name__
                        continue

                    data["action_args"].append({"name": name, "type": ttype.__name__})

                except AttributeError:
                    print(f"Skipping {ttype}")  # TODO make a fix for Union

            if type_name not in object_actions:
                object_actions[type_name] = []
            object_actions[type_name].append(data)

    for obj_type, obj in OBJECT_TYPES.items():

        if "built-in" in obj and obj["built-in"]:  # built-in types are already there
            continue

        # db-stored (user-created) object types
        db = mongo.arcor2
        obj = await db.object_types.find_one({"_id": obj_type})
        try:
            object_actions[obj_type] = generate_source.get_object_actions(obj["source"])
        except Exception as e:
            await logger.error(e)

    # add actions from ancestors
    for obj_type in OBJECT_TYPES.keys():
        add_ancestor_actions(obj_type, object_actions)

    OBJECT_ACTIONS = object_actions


def add_ancestor_actions(obj_type, object_actions):

    if "base" not in OBJECT_TYPES[obj_type]:
        return

    base = OBJECT_TYPES[obj_type]["base"]

    if base:
        if "base" in base and base["base"]:
            add_ancestor_actions(base, object_actions)

        # do not add action from base if it is overridden in child
        for base_action in object_actions[base]:
            for obj_action in object_actions[obj_type]:
                if base_action["name"] == obj_action["name"]:

                    # built-in object has no "origins" yet
                    if "origins" not in obj_action:
                        obj_action["origins"] = base
                    break
            else:
                action = base_action.copy()
                if "origins" not in action:
                    action["origins"] = base
                object_actions[obj_type].append(action)


@rpc(logger)
async def get_object_actions(req, ui, args) -> Dict:

    assert "type" in args

    msg = response(req)
    try:
        msg["data"] = OBJECT_ACTIONS[args["type"]]
    except KeyError:
        return response(req, False, [f'Unknown object type: {args["type"]}.'])

    return msg


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


async def register(websocket) -> None:
    await logger.info("Registering new ui")
    INTERFACES.add(websocket)
    await notify_scene(websocket)
    await notify_project(websocket)


async def unregister(websocket) -> None:
    await logger.info("Unregistering ui")  # TODO print out some identifier
    INTERFACES.remove(websocket)


@validate_event(logger, VALIDATE_SCENE)
async def scene_change(ui, scene) -> None:

    SCENE.update(scene)
    await notify_scene_change_to_others(ui)


@validate_event(logger, VALIDATE_PROJECT)
async def project_change(ui, project) -> None:

    PROJECT.update(project)
    await notify_project_change_to_others(ui)


RPC_DICT: Dict = {'getObjectTypes': get_object_types,
                  'getObjectActions': get_object_actions,
                  'saveProject': save_project,
                  'saveScene': save_scene}

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

    asyncio.get_event_loop().set_debug(enabled=True)
    asyncio.get_event_loop().run_until_complete(multiple_tasks())
    asyncio.get_event_loop().run_forever()


if __name__ == "__main__":
    main()
