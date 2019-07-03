#!/usr/bin/env python3
# -*- coding: utf-8 -*-


import asyncio
import json
import websockets
import functools
import sys
from typing import Dict, List, Set, Optional
import inspect
from arcor2.core import WorldObject
import arcor2.core
import arcor2.user_objects
import arcor2.projects
from arcor2 import generate_source
import importlib
from typing import get_type_hints
from aiologger import Logger
import motor.motor_asyncio
import aiofiles
import os
from arcor2.manager import RPC_DICT as MANAGER_RPC_DICT


# TODO validation of scene/project -> in thread pool executor (CPU intensive)
# TODO read additional objects' locations from env. variable and import them dynamically on start

logger = Logger.with_default_handlers(name='arcor2-server')

mongo = motor.motor_asyncio.AsyncIOMotorClient()

SCENE: Dict = {}
PROJECT: Dict = {}
INTERFACES: Set = set()

# TODO
MANAGER_RPC_REQUEST_QUEUE = asyncio.Queue()
MANAGER_RPC_RESPONSE_QUEUE = asyncio.Queue()

MANAGER_RPC_REQ_ID = 0


async def handle_manager_incoming_messages(manager_client):

    try:

        async for message in manager_client:

            msg = json.loads(message)
            await logger.info("Message from manager: {}".format(msg))

            if "event" in msg:
                await asyncio.wait([intf.send(json.dumps(msg)) for intf in INTERFACES])
            elif "response" in msg:
                await MANAGER_RPC_RESPONSE_QUEUE.put(msg)

    except websockets.exceptions.ConnectionClosed:
        await logger.error("Connection to manager closed.")
        # TODO try to open it again and refuse requests meanwhile


async def project_manager_client():

    async with websockets.client.connect("ws://localhost:6790") as manager_client:

        asyncio.ensure_future(handle_manager_incoming_messages(manager_client))

        while True:
            msg = await MANAGER_RPC_REQUEST_QUEUE.get()
            await manager_client.send(json.dumps(msg))

# TODO log UI id...
# TODO notify RPC requests to other interfaces to let them know what happened?
def rpc(f):
    async def wrapper(req, ui, args):

        msg = await f(req, ui, args)
        j = json.dumps(msg)
        await asyncio.wait([ui.send(j)])
        await logger.debug("RPC request: {}, args: {}, result: {}".format(req, args, j))

    return wrapper


def response(resp_to: str, result: bool = True, messages: Optional[List[str]] = None) -> Dict:

    if messages is None:
        messages = []

    return {"response": resp_to, "result": result, "messages": messages}


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


@rpc
async def get_object_types(req, ui, args) -> Dict:

    msg = response(req)
    msg["data"] = []

    modules = (arcor2.core, arcor2.user_objects)

    for module in modules:
        for cls in inspect.getmembers(module, inspect.isclass):
            if not issubclass(cls[1], WorldObject):
                continue

            # TODO ancestor
            msg["data"].append({"type": "{}/{}".format(module.__name__, cls[0]), "description": cls[1].__DESCRIPTION__})

    return msg


@rpc
async def save_scene(req, ui, args) -> Dict:

    if "_id" not in SCENE:
        return response(req, False, ["Scene not opened or invalid."])

    msg = response(req)

    db = mongo.arcor2

    old_scene = await db.scenes.find_one({"_id": SCENE["_id"]})
    if old_scene:
        result = await db.scenes.replace_one({'_id': old_scene["_id"]}, SCENE)
        await logger.debug("scene updated")
    else:
        result = await db.scenes.insert_one(SCENE)
        await logger.debug("scene created")

    return msg


@rpc
async def save_project(req, ui, args) -> Dict:

    if "_id" not in PROJECT:
        return response(req, False, ["Project not opened or invalid."])

    db = mongo.arcor2
    # TODO validate project here or in DB?

    old_project = await db.projects.find_one({"_id": PROJECT["_id"]})
    if old_project:
        result = await db.projects.replace_one({'_id': old_project["_id"]}, PROJECT)
        await logger.debug("project updated")
    else:
        result = await db.projects.insert_one(PROJECT)
        await logger.debug("project created")

    action_names = []

    try:
        for obj in PROJECT["objects"]:
            for aps in obj["action_points"]:
                for act in aps["actions"]:
                    action_names.append(act["id"])
    except KeyError as e:
        await logger.error("Project data invalid: {}".format(e))
        return response(req, False, ["Project data invalid!", str(e)])

    project_path = os.path.join(arcor2.projects.__path__[0], PROJECT["_id"])

    if not os.path.exists(project_path):
        os.makedirs(project_path)

        async with aiofiles.open(os.path.join(project_path, "__init__.py"), mode='w') as f:
            pass

    async with aiofiles.open(os.path.join(project_path, "resources.py"), mode='w') as f:
        await f.write(generate_source.derived_resources_class(PROJECT["_id"], action_names))

    script_path = os.path.join(project_path, "script.py")

    async with aiofiles.open(script_path, mode='w') as f:
        await f.write(generate_source.SCRIPT_HEADER)
        await f.write(generate_source.program_src(PROJECT, SCENE))

    generate_source.make_executable(script_path)

    return response(req)


@rpc
async def get_object_actions(req, ui, args) -> Dict:

    try:
        module_name, cls_name = args["type"].split('/')
    except (TypeError, ValueError):
        await asyncio.wait([ui.send(json.dumps(response(req, False, ["Invalid module or object type."])))])
        return

    msg = response(req)
    msg["data"] = []

    module = importlib.import_module(module_name)
    cls = getattr(module, cls_name)

    # ...inspect.ismethod does not work on un-initialized classes
    for method in inspect.getmembers(cls, predicate=inspect.isfunction):

        if not hasattr(method[1], "__action__"):
            continue

        meta = method[1].__action__

        data = {"name": method[0], "blocking": meta.blocking, "free": meta.free, "composite": False, "blackbox": False,
         "action_args": []}

        for name, ttype in get_type_hints(method[1]).items():

            try:

                if name == "return":
                    data["returns"] = ttype.__name__
                    continue

                data["action_args"].append({"name": name, "type": ttype.__name__})

            except AttributeError:
                print("Skipping {}".format(ttype))  # TODO make a fix for Union

        msg["data"].append(data)

    return msg


@rpc
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


async def scene_change(ui, scene) -> None:
    SCENE.update(scene)
    await notify_scene_change_to_others(ui)


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


async def server(ui, path, extra_argument) -> None:

    await register(ui)
    try:
        async for message in ui:

            try:
                data = json.loads(message)
            except json.decoder.JSONDecodeError as e:
                await logger.error(e)
                continue

            if "request" in data:  # ...then it is RPC
                try:
                    rpc_func = RPC_DICT[data['request']]
                except KeyError as e:
                    await logger.error("Unknown RPC request: {}.".format(e))
                    continue

                await rpc_func(data['request'], ui, data.get("args", {}))

            elif "event" in data:  # ...event from UI

                try:
                    event_func = EVENT_DICT[data["event"]]
                except KeyError as e:
                    await logger.error("Unknown event type: {}.".format(e))
                    continue

                await event_func(ui, data["data"])

            else:
                await logger.error("unsupported format of message: {}".format(data))
    finally:
        await unregister(ui)


async def multiple_tasks():

    bound_handler = functools.partial(server, extra_argument='spam')

    input_coroutines = [websockets.serve(bound_handler, '0.0.0.0', 6789), project_manager_client()]
    res = await asyncio.gather(*input_coroutines, return_exceptions=True)
    return res


def main():

    assert sys.version_info >= (3, 6)

    asyncio.get_event_loop().set_debug(enabled=True)
    asyncio.get_event_loop().run_until_complete(multiple_tasks())
    asyncio.get_event_loop().run_forever()


if __name__ == "__main__":
    main()
