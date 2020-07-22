#!/usr/bin/env python3
# -*- coding: utf-8 -*-


import argparse
import asyncio
import functools
import inspect
import json
import os
import shutil
import sys
import uuid
from typing import get_type_hints

from aiologger.levels import LogLevel  # type: ignore

from aiorun import run  # type: ignore

from dataclasses_jsonschema import ValidationError

import websockets
from websockets.server import WebSocketServerProtocol as WsClient

import arcor2
import arcor2.helpers as hlp
from arcor2 import action as action_mod
from arcor2.clients import aio_persistent_storage as storage
from arcor2.data import common, compile_json_schemas, events
from arcor2.data import rpc
from arcor2.data.helpers import EVENT_MAPPING, RPC_MAPPING
from arcor2.exceptions import Arcor2Exception
from arcor2.nodes.execution import RPC_DICT as EXE_RPC_DICT
from arcor2.parameter_plugins import PARAM_PLUGINS
from arcor2.server import events as server_events, execution as exe, globals as glob, notifications as notif, \
    objects_services_actions as osa, rpc as srpc, settings

# disables before/after messages, etc.
action_mod.HANDLE_ACTIONS = False


async def handle_manager_incoming_messages(manager_client) -> None:

    try:

        async for message in manager_client:

            msg = json.loads(message)

            if "event" in msg:

                if glob.INTERFACES:
                    await asyncio.gather(*[hlp.send_json_to_client(intf, message) for intf in glob.INTERFACES])

                try:
                    evt = EVENT_MAPPING[msg["event"]].from_dict(msg)
                except ValidationError as e:
                    await glob.logger.error("Invalid event: {}, error: {}".format(msg, e))
                    continue

                if isinstance(evt, events.PackageInfoEvent):
                    glob.PACKAGE_INFO = evt.data
                elif isinstance(evt, events.PackageStateEvent):
                    glob.PACKAGE_STATE = evt.data

                    if evt.data.state == common.PackageStateEnum.STOPPED:

                        if not glob.TEMPORARY_PACKAGE:
                            # after (ordinary) package is finished, show list of packages
                            glob.MAIN_SCREEN = \
                                events.ShowMainScreenData(events.ShowMainScreenData.WhatEnum.PackagesList)
                            await notif.broadcast_event(events.ShowMainScreenEvent(
                                data=events.ShowMainScreenData(events.ShowMainScreenData.WhatEnum.PackagesList,
                                                               evt.data.package_id)))

                        # temporary package is handled elsewhere
                        server_events.package_stopped.set()
                        server_events.package_started.clear()

                        glob.CURRENT_ACTION = None
                        glob.ACTION_STATE = None
                        glob.PACKAGE_INFO = None

                    else:
                        server_events.package_stopped.clear()
                        server_events.package_started.set()

                elif isinstance(evt, events.ActionStateEvent):
                    glob.ACTION_STATE = evt.data
                elif isinstance(evt, events.CurrentActionEvent):
                    glob.CURRENT_ACTION = evt.data
                elif isinstance(evt, events.ProjectExceptionEvent):
                    pass
                else:
                    await glob.logger.warn(f"Unhandled type of event from Execution: {evt.event}")

            elif "response" in msg:

                # TODO handle potential errors
                _, resp_cls = RPC_MAPPING[msg["response"]]
                resp = resp_cls.from_dict(msg)
                exe.MANAGER_RPC_RESPONSES[resp.id].put_nowait(resp)

    except websockets.exceptions.ConnectionClosed:
        await glob.logger.error("Connection to manager closed.")


async def _initialize_server() -> None:

    exe_version = await exe.manager_request(rpc.common.VersionRequest(uuid.uuid4().int))
    assert isinstance(exe_version, rpc.common.VersionResponse)

    """
    Following check is especially useful when running server/execution in Docker containers.
    Then it might easily happen that one tries to use different versions together.
    """
    try:
        hlp.check_compatibility(arcor2.api_version(), exe_version.data.version)
    except Arcor2Exception as e:
        raise Arcor2Exception("ARServer/Execution API_VERSION mismatch.") from e

    while True:  # wait until Project service becomes available
        try:
            await storage.get_projects()
            break
        except storage.PersistentStorageException as e:
            print(e.message)
            await asyncio.sleep(1)

    await osa.get_object_types()

    bound_handler = functools.partial(hlp.server, logger=glob.logger, register=register, unregister=unregister,
                                      rpc_dict=RPC_DICT, event_dict=EVENT_DICT, verbose=glob.VERBOSE)

    await glob.logger.info("Server initialized.")
    await asyncio.wait([websockets.serve(bound_handler, '0.0.0.0', glob.PORT)])


async def list_meshes_cb(req: rpc.storage.ListMeshesRequest, ui: WsClient) -> rpc.storage.ListMeshesResponse:
    return rpc.storage.ListMeshesResponse(data=await storage.get_meshes())


async def register(websocket: WsClient) -> None:

    await glob.logger.info("Registering new ui")
    glob.INTERFACES.add(websocket)

    if glob.PROJECT:
        assert glob.SCENE
        await notif.event(websocket,
                          events.OpenProject(data=events.OpenProjectData(glob.SCENE.scene, glob.PROJECT.project)))
    elif glob.SCENE:
        await notif.event(websocket, events.OpenScene(data=events.OpenSceneData(glob.SCENE.scene)))
    elif glob.PACKAGE_INFO:

        # this can't be done in parallel - ui expects this order of events
        await websocket.send(events.PackageStateEvent(data=glob.PACKAGE_STATE).to_json())
        await websocket.send(events.PackageInfoEvent(data=glob.PACKAGE_INFO).to_json())

        if glob.ACTION_STATE:
            await websocket.send(events.ActionStateEvent(data=glob.ACTION_STATE).to_json())
        if glob.CURRENT_ACTION:
            await websocket.send(events.CurrentActionEvent(data=glob.CURRENT_ACTION).to_json())
    else:
        await notif.event(websocket, events.ShowMainScreenEvent(data=glob.MAIN_SCREEN))


async def unregister(websocket: WsClient) -> None:
    await glob.logger.info("Unregistering ui")  # TODO print out some identifier
    glob.INTERFACES.remove(websocket)

    for registered_uis in glob.ROBOT_JOINTS_REGISTERED_UIS.values():
        if websocket in registered_uis:
            registered_uis.remove(websocket)
    for registered_uis in glob.ROBOT_EEF_REGISTERED_UIS.values():
        if websocket in registered_uis:
            registered_uis.remove(websocket)


async def system_info_cb(req: rpc.common.SystemInfoRequest, ui: WsClient) -> rpc.common.SystemInfoResponse:

    resp = rpc.common.SystemInfoResponse()
    resp.data.version = arcor2.version()
    resp.data.api_version = arcor2.api_version()
    resp.data.supported_parameter_types = set(PARAM_PLUGINS.keys())
    resp.data.supported_rpc_requests = {key.request for key in RPC_DICT.keys()}
    return resp


RPC_DICT: hlp.RPC_DICT_TYPE = {
    rpc.common.SystemInfoRequest: system_info_cb
}

# discovery of RPC callbacks
for _, rpc_module in inspect.getmembers(srpc, inspect.ismodule):
    for rpc_cb_name, rpc_cb in inspect.getmembers(rpc_module):

        if not rpc_cb_name.endswith("_cb"):
            continue

        hints = get_type_hints(rpc_cb)

        try:
            ttype = hints["req"]
        except KeyError:
            continue

        RPC_DICT[ttype] = rpc_cb

# add Project Manager RPC API
for k, v in EXE_RPC_DICT.items():

    if v.__name__.startswith("_"):
        continue

    RPC_DICT[k] = exe.manager_request


# events from clients
EVENT_DICT: hlp.EVENT_DICT_TYPE = {}


async def aio_main() -> None:

    await asyncio.gather(
        exe.project_manager_client(handle_manager_incoming_messages),
        _initialize_server()
    )


def main() -> None:

    assert sys.version_info >= (3, 8)

    parser = argparse.ArgumentParser()

    parser.add_argument("-v", "--verbose", help="Increase verbosity.",
                        action="store_const", const=True, default=False)
    parser.add_argument("-d", "--debug", help="Set logging level to debug.",
                        action="store_const", const=LogLevel.DEBUG, default=LogLevel.INFO)
    parser.add_argument('--version', action='version', version=arcor2.version(),
                        help="Shows ARCOR2 version and exits.")
    parser.add_argument('--api_version', action='version', version=arcor2.api_version(),
                        help="Shows API version and exits.")
    parser.add_argument("-a", "--asyncio_debug", help="Turn on asyncio debug mode.",
                        action="store_const", const=True, default=False)

    args = parser.parse_args()
    glob.logger.level = args.debug
    glob.VERBOSE = args.verbose

    loop = asyncio.get_event_loop()
    loop.set_debug(enabled=args.asyncio_debug)

    compile_json_schemas()

    if os.path.exists(settings.URDF_PATH):
        shutil.rmtree(settings.URDF_PATH)
    os.makedirs(settings.URDF_PATH)

    run(aio_main(), loop=loop, stop_on_unhandled_errors=True)


if __name__ == "__main__":
    main()
