#!/usr/bin/env python3
# -*- coding: utf-8 -*-


import asyncio
import json
import logging
import websockets
import functools
import sys
from typing import Dict, List
import inspect
from arcor2.core import WorldObject
import arcor2.core
import arcor2.user_objects
import importlib
from typing import get_type_hints

# TODO https://pypi.org/project/aiofiles/
# TODO https://github.com/mongodb/motor

# TODO read additional objects' locations from env. variable and import them dynamically on start

logging.basicConfig(level=logging.INFO)

SCENE = {}
INTERFACES = set()


def response(resp_to: str, result: bool = True, messages: List[str] = []) -> Dict:

    return {"response": resp_to, "result": result, "messages": messages}


def scene_event():
    return json.dumps({"event": "sceneChanged", "data": SCENE})


async def notify_scene_change_to_others(interface=None):
    if len(INTERFACES) > 1:
        message = scene_event()
        await asyncio.wait([intf.send(message) for intf in INTERFACES if intf != interface])


async def notify_scene(interface):
    message = scene_event()
    await asyncio.wait([interface.send(message)])


async def get_object_types(req, ui, args):

    msg = response(req)
    msg["data"] = []

    modules = (arcor2.core, arcor2.user_objects)

    for module in modules:
        for cls in inspect.getmembers(module, inspect.isclass):
            if not issubclass(cls[1], WorldObject):
                continue

            # TODO ancestor
            msg["data"].append({"type": "{}/{}".format(module.__name__, cls[0]), "description": cls[1].__DESCRIPTION__})

    await asyncio.wait([ui.send(json.dumps(msg))])


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

    await asyncio.wait([ui.send(json.dumps(msg))])

async def register(websocket):
    INTERFACES.add(websocket)
    await notify_scene(websocket)


async def unregister(websocket):
    INTERFACES.remove(websocket)


async def scene_change(ui, scene):
    SCENE.update(scene)
    await notify_scene_change_to_others(ui)


RPC_DICT = {'getObjectTypes': get_object_types,
            'getObjectActions': get_object_actions}
EVENT_DICT = {'sceneChanged': scene_change}


async def server(ui, path, extra_argument):
    # register(websocket) sends user_event() to websocket

    await register(ui)
    try:
        async for message in ui:

            try:
                data = json.loads(message)
            except json.decoder.JSONDecodeError as e:
                logging.error(e)
                continue

            if "request" in data:  # then it is RPC
                try:
                    await RPC_DICT[data['request']](data['request'], ui, data["args"])
                except KeyError:
                    pass
            elif "event" in data:

                try:
                    await EVENT_DICT["sceneChanged"](ui, data["data"])
                except KeyError:
                    pass

            else:
                logging.error("unsupported format of message: {}".format(data))
    finally:
        await unregister(ui)


def main():

    assert sys.version_info >= (3, 6)

    bound_handler = functools.partial(server, extra_argument='spam')
    # asyncio.get_event_loop().set_debug(enabled=True)
    asyncio.get_event_loop().run_until_complete(
        websockets.serve(bound_handler, 'localhost', 6789))
    asyncio.get_event_loop().run_forever()


if __name__ == "__main__":
    main()
