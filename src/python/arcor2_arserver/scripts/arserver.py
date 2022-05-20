#!/usr/bin/env python3


import argparse
import asyncio
import functools
import inspect
import shutil
import sys
from typing import get_type_hints

import websockets
from aiologger.levels import LogLevel
from aiorun import run
from dataclasses_jsonschema import ValidationError
from websockets.server import WebSocketServerProtocol as WsClient

import arcor2.helpers as hlp
import arcor2_arserver
import arcor2_arserver_data
import arcor2_execution_data
from arcor2 import env, json, ws_server
from arcor2.clients import aio_scene_service as scene_srv
from arcor2.data import compile_json_schemas, events, rpc
from arcor2.exceptions import Arcor2Exception
from arcor2.parameter_plugins.utils import known_parameter_types
from arcor2_arserver import events as server_events
from arcor2_arserver import execution as exe
from arcor2_arserver import globals as glob
from arcor2_arserver import logger, models
from arcor2_arserver import notifications as notif
from arcor2_arserver import objects_actions as osa
from arcor2_arserver import rpc as srpc_callbacks
from arcor2_arserver import scene, settings
from arcor2_arserver.clients import project_service as storage
from arcor2_arserver.lock.notifications import run_lock_notification_worker
from arcor2_arserver_data import events as evts
from arcor2_arserver_data import rpc as srpc
from arcor2_arserver_data.rpc import objects as obj_rpc
from arcor2_execution_data import EVENTS as EXE_EVENTS
from arcor2_execution_data import EXPOSED_RPCS
from arcor2_execution_data import RPCS as EXE_RPCS
from arcor2_runtime import events as runtime_events


async def handle_manager_incoming_messages(manager_client) -> None:

    event_mapping: dict[str, type[events.Event]] = {evt.__name__: evt for evt in EXE_EVENTS}
    rpc_mapping: dict[str, type[rpc.common.RPC]] = {r.__name__: r for r in EXE_RPCS}

    try:

        async for message in manager_client:

            msg = json.loads(message)

            if not isinstance(msg, dict):
                continue

            if "event" in msg:

                if glob.USERS.interfaces:
                    await asyncio.gather(
                        *[ws_server.send_json_to_client(intf, message) for intf in glob.USERS.interfaces]
                    )

                try:
                    evt = event_mapping[msg["event"]].from_dict(msg)
                except ValidationError as e:
                    logger.error("Invalid event: {}, error: {}".format(msg, e))
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

    except websockets.exceptions.ConnectionClosed as e:
        logger.error(f"Connection to manager closed. {str(e)}")


async def _initialize_server() -> None:

    exe_version = await exe.manager_request(rpc.common.Version.Request(exe.get_id()))
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
            logger.error(f"Failed to communicate with Project service. {str(e)}")
            await asyncio.sleep(1)

    while True:
        try:
            if await scene_srv.started():
                logger.warn("Scene already started, attempting to stop it...")
            await scene_srv.stop()  # if not started, call it anyway, it should be instant
            break
        except scene_srv.SceneServiceException as e:
            logger.error(f"Failed to communicate with the Scene service. {str(e)}")
            await asyncio.sleep(1)

    await osa.get_object_types()

    bound_handler = functools.partial(
        ws_server.server,
        logger=logger,
        register=register,
        unregister=unregister,
        rpc_dict=RPC_DICT,
        event_dict=EVENT_DICT,
        verbose=glob.VERBOSE,
    )

    if __debug__:
        logger.warn("Development mode. The service will shutdown on any unhandled exception.")

    logger.info(f"ARServer {arcor2_arserver.version()} " f"(API version {arcor2_arserver_data.version()}) initialized.")
    await asyncio.wait([websockets.server.serve(bound_handler, "0.0.0.0", glob.PORT)])
    asyncio.create_task(run_lock_notification_worker())


async def list_meshes_cb(req: obj_rpc.ListMeshes.Request, ui: WsClient) -> obj_rpc.ListMeshes.Response:
    return obj_rpc.ListMeshes.Response(data=await storage.get_meshes())


async def register(websocket: WsClient) -> None:

    logger.info("Registering new ui")
    glob.USERS.add_interface(websocket)

    if glob.LOCK.project:
        assert glob.LOCK.scene
        await notif.event(
            websocket, evts.p.OpenProject(evts.p.OpenProject.Data(glob.LOCK.scene.scene, glob.LOCK.project.project))
        )
    elif glob.LOCK.scene:
        await notif.event(websocket, evts.s.OpenScene(evts.s.OpenScene.Data(glob.LOCK.scene.scene)))
    elif glob.PACKAGE_INFO:

        # this can't be done in parallel - ui expects this order of events
        await websocket.send(events.PackageState(glob.PACKAGE_STATE).to_json())
        await websocket.send(events.PackageInfo(glob.PACKAGE_INFO).to_json())

        if glob.ACTION_STATE_BEFORE:
            await websocket.send(events.ActionStateBefore(glob.ACTION_STATE_BEFORE).to_json())
    else:
        assert glob.MAIN_SCREEN
        await notif.event(websocket, evts.c.ShowMainScreen(glob.MAIN_SCREEN))

    if glob.LOCK.project or glob.LOCK.scene:
        await notif.event(websocket, scene.get_scene_state())


async def unregister(websocket: WsClient) -> None:

    try:
        user_name = glob.USERS.user_name(websocket)
    except Arcor2Exception:
        logger.info("Unregistering ui")
    else:
        await glob.LOCK.schedule_auto_release(user_name)
        logger.info(f"Unregistering ui {user_name}")

    glob.USERS.logout(websocket)

    logger.debug(f"Known user names: {glob.USERS.user_names}")

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

    modules = [arcor2_execution_data.events, events, runtime_events]

    for _, mod in inspect.getmembers(evts, inspect.ismodule):
        modules.append(mod)

    event_types: list[type[events.Event]] = []

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

    parser = argparse.ArgumentParser()

    parser.add_argument("-v", "--verbose", help="Increase verbosity.", action="store_const", const=True, default=False)
    parser.add_argument(
        "-d",
        "--debug",
        help="Set logging level to debug.",
        action="store_const",
        const=LogLevel.DEBUG,
        default=LogLevel.DEBUG if env.get_bool("ARCOR2_ARSERVER_DEBUG") else LogLevel.INFO,
    )
    parser.add_argument(
        "--version", action="version", version=arcor2_arserver.version(), help="Shows version and exits."
    )
    parser.add_argument(
        "--api_version", action="version", version=arcor2_arserver_data.version(), help="Shows API version and exits."
    )
    parser.add_argument(
        "-a",
        "--asyncio_debug",
        help="Turn on asyncio debug mode.",
        action="store_const",
        const=True,
        default=env.get_bool("ARCOR2_ARSERVER_ASYNCIO_DEBUG"),
    )
    parser.add_argument("--openapi", action="store_true", help="Prints OpenAPI models and exits.")

    args = parser.parse_args()

    if args.openapi:
        print_openapi_models()
        return

    logger.level = args.debug
    glob.VERBOSE = args.verbose

    loop = asyncio.get_event_loop()
    loop.set_debug(enabled=args.asyncio_debug)
    loop.set_exception_handler(ws_server.custom_exception_handler)

    compile_json_schemas()

    run(aio_main(), loop=loop)

    shutil.rmtree(settings.OBJECT_TYPE_PATH)


if __name__ == "__main__":
    main()
