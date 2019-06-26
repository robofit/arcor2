#!/usr/bin/env python3
# -*- coding: utf-8 -*-


import asyncio
import json
import logging
import websockets
import functools
import sys
from typing import Dict, List, Set
import inspect
from arcor2.core import WorldObject
import arcor2.core
import arcor2.user_objects
import importlib
from typing import get_type_hints
from aiologger import Logger
import motor.motor_asyncio


# TODO https://pypi.org/project/aiofiles/

# TODO read additional objects' locations from env. variable and import them dynamically on start

logger = Logger.with_default_handlers(name='arcor2-server')

mongo = motor.motor_asyncio.AsyncIOMotorClient()

PROJECT_ID = "demo_v0"
SCENE: Dict = {}
PROJECT: Dict = {}
INTERFACES: Set = set()


def rpc(f):  # TODO log UI id...
    async def wrapper(req, ui, args):

        msg = await f(req, ui, args)
        j = json.dumps(msg)
        await asyncio.wait([ui.send(j)])
        await logger.debug("RPC request: {}, args: {}, result: {}".format(req, args, j))

    return wrapper


def response(resp_to: str, result: bool = True, messages: List[str] = []) -> Dict:

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
async def get_object_types(req, ui, args) -> None:

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
async def save_scene(req, ui, args):

    assert "scene_id" in SCENE

    msg = response(req)

    db = mongo.arcor2

    result = await db.scenes.insert_one(SCENE)
    # TODO check result

    return msg


@rpc
async def save_project(req, ui, args):

    assert "project_id" in PROJECT

    msg = response(req)

    db = mongo.arcor2
    # TODO validate project here or in DB?
    result = await db.projects.insert_one(PROJECT)
    # TODO check result

    # TODO generate Resources class
    # TODO generate script

    return msg


@rpc
async def get_object_actions(req, ui, args):

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


async def register(websocket) -> None:
    INTERFACES.add(websocket)
    await notify_scene(websocket)
    await notify_project(websocket)


async def unregister(websocket) -> None:
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

EVENT_DICT: Dict = {'sceneChanged': scene_change,
              'projectChanged': project_change}


async def server(ui, path, extra_argument) -> None:

    await register(ui)
    try:
        async for message in ui:

            print(message)
            try:
                data = json.loads(message)
            except json.decoder.JSONDecodeError as e:
                logging.error(e)
                continue

            if "request" in data:  # then it is RPC
                try:
                    await RPC_DICT[data['request']](data['request'], ui, data["args"])
                except KeyError as e:
                    logging.error(e)

            elif "event" in data:

                try:
                    await EVENT_DICT[data["event"]](ui, data["data"])
                except KeyError as e:
                    logging.error(e)

            else:
                logging.error("unsupported format of message: {}".format(data))
    finally:
        await unregister(ui)


def main():

    assert sys.version_info >= (3, 6)

    bound_handler = functools.partial(server, extra_argument='spam')
    # asyncio.get_event_loop().set_debug(enabled=True)
    asyncio.get_event_loop().run_until_complete(
        websockets.serve(bound_handler, '0.0.0.0', 6789))
    asyncio.get_event_loop().run_forever()


if __name__ == "__main__":
    main()
