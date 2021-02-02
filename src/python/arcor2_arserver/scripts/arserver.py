#!/usr/bin/env python3


import argparse
import asyncio
import functools
import inspect
import json
import os
import shutil
import sys
import uuid
from typing import Dict, List, Type, get_type_hints

import websockets
from aiologger.levels import LogLevel
from aiorun import run
from dataclasses_jsonschema import ValidationError
from websockets.server import WebSocketServerProtocol as WsClient

import arcor2.helpers as hlp
import arcor2_arserver
import arcor2_arserver_data
import arcor2_execution_data
from arcor2 import action as action_mod
from arcor2 import ws_server
from arcor2.data import compile_json_schemas, events, rpc
from arcor2.exceptions import Arcor2Exception
from arcor2.parameter_plugins.utils import known_parameter_types
from arcor2_arserver import events as server_events
from arcor2_arserver import execution as exe
from arcor2_arserver import globals as glob
from arcor2_arserver import models
from arcor2_arserver import notifications as notif
from arcor2_arserver import objects_actions as osa
from arcor2_arserver import rpc as srpc_callbacks
from arcor2_arserver import settings
from arcor2_arserver.clients import persistent_storage as storage
from arcor2_arserver_data import events as evts
from arcor2_arserver_data import rpc as srpc
from arcor2_arserver_data.rpc import objects as obj_rpc
from arcor2_execution_data import EVENTS as EXE_EVENTS
from arcor2_execution_data import EXPOSED_RPCS
from arcor2_execution_data import RPCS as EXE_RPCS

# disables before/after messages, etc.
action_mod.HANDLE_ACTIONS = False


async def handle_manager_incoming_messages(manager_client) -> None:

    event_mapping: Dict[str, Type[events.Event]] = {evt.__name__: evt for evt in EXE_EVENTS}
    rpc_mapping: Dict[str, Type[rpc.common.RPC]] = {r.__name__: r for r in EXE_RPCS}

    try:

        async for message in manager_client:

            msg = json.loads(message)

            if "event" in msg:

                if glob.INTERFACES:
                    await asyncio.gather(*[ws_server.send_json_to_client(intf, message) for intf in glob.INTERFACES])

                try:
                    evt = event_mapping[msg["event"]].from_dict(msg)
                except ValidationError as e:
                    glob.logger.error("Invalid event: {}, error: {}".format(msg, e))
                    continue

                if isinstance(evt, events.PackageInfo):
                    glob.PACKAGE_INFO = evt.data
                elif isinstance(evt, events.PackageState):
                    glob.PACKAGE_STATE = evt.data

                    if evt.data.state == events.PackageState.Data.StateEnum.STOPPED:

                        if not glob.TEMPORARY_PACKAGE:
                            # after (ordinary) package is finished, show list of packages
                            glob.MAIN_SCREEN = evts.c.ShowMainScreen.Data(
                                evts.c.ShowMainScreen.Data.WhatEnum.PackagesList
                            )
                            await notif.broadcast_event(
                                evts.c.ShowMainScreen(
                                    evts.c.ShowMainScreen.Data(
                                        evts.c.ShowMainScreen.Data.WhatEnum.PackagesList, evt.data.package_id
                                    )
                                )
                            )

                        # temporary package is handled elsewhere
                        server_events.package_stopped.set()
                        server_events.package_started.clear()

                        glob.ACTION_STATE_BEFORE = None
                        glob.PACKAGE_INFO = None

                    else:
                        server_events.package_stopped.clear()
                        server_events.package_started.set()

                elif isinstance(evt, events.ActionStateBefore):
                    glob.ACTION_STATE_BEFORE = evt.data

            elif "response" in msg:

                # TODO handle potential errors
                rpc_cls = rpc_mapping[msg["response"]]
                resp = rpc_cls.Response.from_dict(msg)
                exe.MANAGER_RPC_RESPONSES[resp.id].put_nowait(resp)

    except websockets.exceptions.ConnectionClosed:
        glob.logger.error("Connection to manager closed.")


async def _initialize_server() -> None:

    exe_version = await exe.manager_request(rpc.common.Version.Request(uuid.uuid4().int))
    assert isinstance(exe_version, rpc.common.Version.Response)
    if not exe_version.result:
        raise Arcor2Exception("Failed to get Execution version.")

    assert exe_version.data is not None

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
        except storage.ProjectServiceException as e:
            print(str(e))
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


async def list_meshes_cb(req: obj_rpc.ListMeshes.Request, ui: WsClient) -> obj_rpc.ListMeshes.Response:
    return obj_rpc.ListMeshes.Response(data=await storage.get_meshes())


async def register(websocket: WsClient) -> None:

    glob.logger.info("Registering new ui")
    glob.INTERFACES.add(websocket)

    if glob.PROJECT:
        assert glob.SCENE
        await notif.event(
            websocket, evts.p.OpenProject(evts.p.OpenProject.Data(glob.SCENE.scene, glob.PROJECT.project))
        )
    elif glob.SCENE:
        await notif.event(websocket, evts.s.OpenScene(evts.s.OpenScene.Data(glob.SCENE.scene)))
    elif glob.PACKAGE_INFO:

        # this can't be done in parallel - ui expects this order of events
        await websocket.send(events.PackageState(glob.PACKAGE_STATE).to_json())
        await websocket.send(events.PackageInfo(glob.PACKAGE_INFO).to_json())

        if glob.ACTION_STATE_BEFORE:
            await websocket.send(events.ActionStateBefore(glob.ACTION_STATE_BEFORE).to_json())
    else:
        assert glob.MAIN_SCREEN
        await notif.event(websocket, evts.c.ShowMainScreen(glob.MAIN_SCREEN))


async def unregister(websocket: WsClient) -> None:
    glob.logger.info("Unregistering ui")  # TODO print out some identifier
    glob.INTERFACES.remove(websocket)

    for registered_uis in glob.ROBOT_JOINTS_REGISTERED_UIS.values():
        if websocket in registered_uis:
            registered_uis.remove(websocket)
    for registered_uis in glob.ROBOT_EEF_REGISTERED_UIS.values():
        if websocket in registered_uis:
            registered_uis.remove(websocket)


async def system_info_cb(req: srpc.c.SystemInfo.Request, ui: WsClient) -> srpc.c.SystemInfo.Response:

    resp = srpc.c.SystemInfo.Response()
    resp.data = resp.Data(
        arcor2_arserver.version(),
        arcor2_arserver_data.version(),
        known_parameter_types(),
        {key for key in RPC_DICT.keys()},
    )
    return resp


RPC_DICT: ws_server.RPC_DICT_TYPE = {srpc.c.SystemInfo.__name__: (srpc.c.SystemInfo, system_info_cb)}

# discovery of RPC callbacks
# TODO refactor it into arcor2 package (to be used by arcor2_execution)
for _, rpc_module in inspect.getmembers(srpc_callbacks, inspect.ismodule):
    for rpc_cb_name, rpc_cb in inspect.getmembers(rpc_module):

        if not rpc_cb_name.endswith("_cb"):
            continue

        hints = get_type_hints(rpc_cb)

        req_cls = hints["req"]
        rpc_cls = getattr(sys.modules[req_cls.__module__], req_cls.__qualname__.split(".")[0])

        RPC_DICT[rpc_cls.__name__] = (rpc_cls, rpc_cb)

# add Project Manager RPC API
for exposed_rpc in EXPOSED_RPCS:
    RPC_DICT[exposed_rpc.__name__] = (exposed_rpc, exe.manager_request)


# events from clients
EVENT_DICT: ws_server.EVENT_DICT_TYPE = {}


async def aio_main() -> None:

    await asyncio.gather(exe.project_manager_client(handle_manager_incoming_messages), _initialize_server())


def print_openapi_models() -> None:

    modules = [arcor2_execution_data.events, events]

    for _, mod in inspect.getmembers(evts, inspect.ismodule):
        modules.append(mod)

    event_types: List[Type[events.Event]] = []

    for mod in modules:
        for _, cls in inspect.getmembers(mod, inspect.isclass):
            if issubclass(cls, events.Event):
                event_types.append(cls)

    print(
        models.generate_openapi(
            "ARCOR2 ARServer", arcor2_arserver.version(), [v[0] for k, v in RPC_DICT.items()], event_types
        )
    )


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
    parser.add_argument("--openapi", action="store_true", help="Prints OpenAPI models and exits.")

    args = parser.parse_args()

    if args.openapi:
        print_openapi_models()
        return

    glob.logger.level = args.debug
    glob.VERBOSE = args.verbose

    loop = asyncio.get_event_loop()
    loop.set_debug(enabled=args.asyncio_debug)

    compile_json_schemas()

    if os.path.exists(settings.URDF_PATH):
        shutil.rmtree(settings.URDF_PATH)
    os.makedirs(settings.URDF_PATH)

    run(aio_main(), loop=loop, stop_on_unhandled_errors=True)

    shutil.rmtree(settings.OBJECT_TYPE_PATH)


if __name__ == "__main__":
    main()
