#!/usr/bin/env python3
# -*- coding: utf-8 -*-


import asyncio
import json
import logging
import websockets
import functools
import sys

# TODO https://pypi.org/project/aiofiles/
# TODO https://github.com/mongodb/motor

logging.basicConfig(level=logging.INFO)

SCENE = {}
INTERFACES = set()


def scene_event():
    return json.dumps({"event": "sceneChanged", "data": SCENE})


async def notify_scene_change_to_others(interface=None):
    if len(INTERFACES) > 1:
        message = scene_event()
        await asyncio.wait([intf.send(message) for intf in INTERFACES if intf != interface])


async def notify_scene(interface):
    message = scene_event()
    await asyncio.wait([interface.send(message)])


async def get_object_types(ui, args):

    # TODO get actual data
    message = '{"response": "getObjectTypes", "result": true, "messages": [], "data": [{"type": "kinali.objects/Tester", "description": "Generic tester.", "ancestor": "arcor2.core/WorldObject"}]}'
    await asyncio.wait([ui.send(message)])


async def register(websocket):
    INTERFACES.add(websocket)
    await notify_scene(websocket)


async def unregister(websocket):
    INTERFACES.remove(websocket)


async def scene_change(ui, scene):
    SCENE.update(scene)
    await notify_scene_change_to_others(ui)


RPC_DICT = {'getObjectTypes': get_object_types}
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
                    await RPC_DICT[data['request']](ui, data["args"])
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
