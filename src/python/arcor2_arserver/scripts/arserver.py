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

import websockets
from aiologger.levels import LogLevel  # type: ignore
from aiorun import run  # type: ignore
from dataclasses_jsonschema import ValidationError
from websockets.server import WebSocketServerProtocol as WsClient

import arcor2.helpers as hlp
import arcor2_arserver
import arcor2_arserver_data
import arcor2_execution_data
from arcor2 import action as action_mod
from arcor2 import ws_server
from arcor2.data import common, compile_json_schemas, events, rpc
from arcor2.data.helpers import EVENT_MAPPING, RPC_MAPPING
from arcor2.data.utils import generate_swagger
from arcor2.exceptions import Arcor2Exception
from arcor2.parameter_plugins import PARAM_PLUGINS
from arcor2_arserver import events as server_events
from arcor2_arserver import execution as exe
from arcor2_arserver import globals as glob
from arcor2_arserver import notifications as notif
from arcor2_arserver import objects_actions as osa
from arcor2_arserver import rpc as srpc_callbacks
from arcor2_arserver import settings
from arcor2_arserver.clients import persistent_storage as storage
from arcor2_arserver.object_types.source import prepare_object_types_dir
from arcor2_arserver_data import events as evts
from arcor2_arserver_data import rpc as srpc
from arcor2_arserver_data.rpc import objects as obj_rpc
from arcor2_execution_data import exposed_rpcs as exe_exposed_rpcs

# disables before/after messages, etc.
action_mod.HANDLE_ACTIONS = False


async def handle_manager_incoming_messages(manager_client) -> None:

    try:

        async for message in manager_client:

            msg = json.loads(message)

            if "event" in msg:

                if glob.INTERFACES:
                    await asyncio.gather(*[ws_server.send_json_to_client(intf, message) for intf in glob.INTERFACES])

                try:
                    evt = EVENT_MAPPING[msg["event"]].from_dict(msg)
                except ValidationError as e:
                    glob.logger.error("Invalid event: {}, error: {}".format(msg, e))
                    continue

                if isinstance(evt, events.PackageInfoEvent):
                    glob.PACKAGE_INFO = evt.data
                elif isinstance(evt, events.PackageStateEvent):
                    glob.PACKAGE_STATE = evt.data

                    if evt.data.state == common.PackageStateEnum.STOPPED:

                        if not glob.TEMPORARY_PACKAGE:
                            # after (ordinary) package is finished, show list of packages
                            glob.MAIN_SCREEN = evts.c.ShowMainScreenData(
                                evts.c.ShowMainScreenData.WhatEnum.PackagesList
                            )
                            await notif.broadcast_event(
                                evts.c.ShowMainScreenEvent(
                                    data=evts.c.ShowMainScreenData(
                                        evts.c.ShowMainScreenData.WhatEnum.PackagesList, evt.data.package_id
                                    )
                                )
                            )

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

            elif "response" in msg:

                # TODO handle potential errors
                _, resp_cls = RPC_MAPPING[msg["response"]]
                resp = resp_cls.from_dict(msg)
                exe.MANAGER_RPC_RESPONSES[resp.id].put_nowait(resp)

    except websockets.exceptions.ConnectionClosed:
        glob.logger.error("Connection to manager closed.")


async def _initialize_server() -> None:

    exe_version = await exe.manager_request(rpc.common.VersionRequest(uuid.uuid4().int))
    assert isinstance(exe_version, rpc.common.VersionResponse)

    """
    Following check is especially useful when running server/execution in Docker containers.
    Then it might easily happen that one tries to use different versions together.
    """
    try:
        hlp.check_compatibility(arcor2_execution_data.version(), exe_version.data.version)
    except Arcor2Exception as e:
        raise Arcor2Exception("ARServer/Execution uses different versions of arcor2_execution_data.") from e

    while True:  # wait until Project service becomes available
        try:
            await storage.initialize_module()
            break
        except storage.PersistentStorageException as e:
            print(e.message)
            await asyncio.sleep(1)

    await osa.get_object_types()

    bound_handler = functools.partial(
        ws_server.server,
        logger=glob.logger,
        register=register,
        unregister=unregister,
        rpc_dict=RPC_DICT,
        event_dict=EVENT_DICT,
        verbose=glob.VERBOSE,
    )

    glob.logger.info("Server initialized.")
    await asyncio.wait([websockets.serve(bound_handler, "0.0.0.0", glob.PORT)])


async def list_meshes_cb(req: obj_rpc.ListMeshesRequest, ui: WsClient) -> obj_rpc.ListMeshesResponse:
    return obj_rpc.ListMeshesResponse(data=await storage.get_meshes())


async def register(websocket: WsClient) -> None:

    glob.logger.info("Registering new ui")
    glob.INTERFACES.add(websocket)

    if glob.PROJECT:
        assert glob.SCENE
        await notif.event(
            websocket, evts.p.OpenProject(data=evts.p.OpenProjectData(glob.SCENE.scene, glob.PROJECT.project))
        )
    elif glob.SCENE:
        await notif.event(websocket, evts.s.OpenScene(data=evts.s.OpenSceneData(glob.SCENE.scene)))
    elif glob.PACKAGE_INFO:

        # this can't be done in parallel - ui expects this order of events
        await websocket.send(events.PackageStateEvent(data=glob.PACKAGE_STATE).to_json())
        await websocket.send(events.PackageInfoEvent(data=glob.PACKAGE_INFO).to_json())

        if glob.ACTION_STATE:
            await websocket.send(events.ActionStateEvent(data=glob.ACTION_STATE).to_json())
        if glob.CURRENT_ACTION:
            await websocket.send(events.CurrentActionEvent(data=glob.CURRENT_ACTION).to_json())
    else:
        await notif.event(websocket, evts.c.ShowMainScreenEvent(data=glob.MAIN_SCREEN))


async def unregister(websocket: WsClient) -> None:
    glob.logger.info("Unregistering ui")  # TODO print out some identifier
    glob.INTERFACES.remove(websocket)

    for registered_uis in glob.ROBOT_JOINTS_REGISTERED_UIS.values():
        if websocket in registered_uis:
            registered_uis.remove(websocket)
    for registered_uis in glob.ROBOT_EEF_REGISTERED_UIS.values():
        if websocket in registered_uis:
            registered_uis.remove(websocket)


async def system_info_cb(req: srpc.c.SystemInfoRequest, ui: WsClient) -> srpc.c.SystemInfoResponse:

    resp = srpc.c.SystemInfoResponse()
    resp.data.version = arcor2_arserver.version()
    resp.data.api_version = arcor2_arserver_data.version()
    resp.data.supported_parameter_types = set(PARAM_PLUGINS.keys())
    resp.data.supported_rpc_requests = {key.request for key in RPC_DICT.keys()}
    return resp


RPC_DICT: ws_server.RPC_DICT_TYPE = {srpc.c.SystemInfoRequest: system_info_cb}

# discovery of RPC callbacks
for _, rpc_module in inspect.getmembers(srpc_callbacks, inspect.ismodule):
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
for exposed_rpc in exe_exposed_rpcs:
    RPC_DICT[exposed_rpc] = exe.manager_request


# events from clients
EVENT_DICT: ws_server.EVENT_DICT_TYPE = {}


async def aio_main() -> None:

    await asyncio.gather(exe.project_manager_client(handle_manager_incoming_messages), _initialize_server())


def swagger_models() -> None:

    modules = []

    for package in (srpc, evts, arcor2_execution_data.events, arcor2_execution_data.rpc):
        for _, mod in inspect.getmembers(package, inspect.ismodule):
            modules.append(mod)

    print(generate_swagger("ARCOR2 ARServer", arcor2_arserver.version(), modules))


def main() -> None:

    assert sys.version_info >= (3, 8)

    parser = argparse.ArgumentParser()

    parser.add_argument("-v", "--verbose", help="Increase verbosity.", action="store_const", const=True, default=False)
    parser.add_argument(
        "-d",
        "--debug",
        help="Set logging level to debug.",
        action="store_const",
        const=LogLevel.DEBUG,
        default=LogLevel.INFO,
    )
    parser.add_argument(
        "--version", action="version", version=arcor2_arserver.version(), help="Shows version and exits."
    )
    parser.add_argument(
        "--api_version", action="version", version=arcor2_arserver_data.version(), help="Shows API version and exits."
    )
    parser.add_argument(
        "-a", "--asyncio_debug", help="Turn on asyncio debug mode.", action="store_const", const=True, default=False
    )
    parser.add_argument("--swagger", action="store_true", help="Prints swagger models and exits.")

    args = parser.parse_args()

    if args.swagger:
        swagger_models()
        return

    glob.logger.level = args.debug
    glob.VERBOSE = args.verbose

    loop = asyncio.get_event_loop()
    loop.set_debug(enabled=args.asyncio_debug)

    compile_json_schemas()

    if os.path.exists(settings.URDF_PATH):
        shutil.rmtree(settings.URDF_PATH)
    os.makedirs(settings.URDF_PATH)

    prepare_object_types_dir(settings.OBJECT_TYPE_PATH, settings.OBJECT_TYPE_MODULE)

    run(aio_main(), loop=loop, stop_on_unhandled_errors=True)


if __name__ == "__main__":
    main()
