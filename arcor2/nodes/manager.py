#!/usr/bin/env python3
# -*- coding: utf-8 -*-


import asyncio
import json
import functools
import sys
from typing import Dict, Union, Set, Callable, List
import argparse
import os

import websockets
from websockets.server import WebSocketServerProtocol
from aiologger import Logger  # type: ignore
import aiofiles  # type: ignore

from arcor2.helpers import response, rpc, server, convert_cc, RpcPlugin, \
    import_cls, ImportClsException, aiologger_formatter
from arcor2.object_types_utils import built_in_types_names
from arcor2.source.utils import make_executable
from arcor2.data import Scene, ObjectType
from arcor2.persistent_storage_client import PersistentStorageClient

logger = Logger.with_default_handlers(name='manager', formatter=aiologger_formatter())

PROCESS: Union[asyncio.subprocess.Process, None] = None
TASK = None

CLIENTS: Set = set()

STORAGE_CLIENT = PersistentStorageClient()

RPC_PLUGINS: List[RpcPlugin] = []

try:
    PROJECT_PATH = os.environ["ARCOR2_PROJECT_PATH"]
except KeyError:
    sys.exit("'ARCOR2_PROJECT_PATH' env. variable not set.")


def process_running() -> bool:

    return PROCESS is not None and PROCESS.returncode is None


async def read_proc_stdout() -> None:

    logger.info("Reading script stdout...")

    assert PROCESS is not None
    assert PROCESS.stdout is not None

    while process_running():
        try:
            stdout = await PROCESS.stdout.readuntil()
        except asyncio.streams.IncompleteReadError:
            break

        try:
            data = json.loads(stdout.decode("utf-8").strip())
            await send_to_clients(data)
        except json.decoder.JSONDecodeError as e:
            await logger.error(e)

    logger.info(f"Process finished with returncode {PROCESS.returncode}.")


@rpc(logger, RPC_PLUGINS)
async def project_run(req: str, client, args: Dict) -> Dict:

    global PROCESS
    global TASK

    if process_running():
        return response(req, False, ["Already running!"])

    path = os.path.join(PROJECT_PATH, "script.py")

    await logger.info(f"Starting script: {path}")
    PROCESS = await asyncio.create_subprocess_exec(path, stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
                                                   stderr=asyncio.subprocess.STDOUT)
    if PROCESS.returncode is None:
        TASK = asyncio.ensure_future(read_proc_stdout())  # run task in background
        return response(req)
    else:
        return response(req, False, ["Failed to start project."])


@rpc(logger, RPC_PLUGINS)
async def project_stop(req: str, client, args: Dict) -> Dict:

    if not process_running():
        return response(req, False, ["Project not running."])

    assert PROCESS is not None
    assert TASK is not None

    await logger.info("Terminating process")
    PROCESS.terminate()
    await logger.info("Waiting for process to finish...")
    await asyncio.wait([TASK])
    return response(req)


@rpc(logger, RPC_PLUGINS)
async def project_pause(req: str, client, args: Dict) -> Dict:

    if not process_running():
        return response(req, False, ["Project not running."])

    assert PROCESS is not None
    assert PROCESS.stdin is not None

    # TODO check if it is not already paused

    PROCESS.stdin.write("p\n".encode())
    await PROCESS.stdin.drain()
    return response(req)


@rpc(logger, RPC_PLUGINS)
async def project_resume(req: str, client, args: Dict) -> Dict:

    if not process_running():
        return response(req, False, ["Project not running."])

    assert PROCESS is not None and PROCESS.stdin is not None

    # TODO check if paused

    PROCESS.stdin.write("r\n".encode())
    await PROCESS.stdin.drain()
    return response(req)


@rpc(logger, RPC_PLUGINS)
async def project_load(req: str, client, args: Dict) -> Dict:

    # TODO check if there are some modifications in already loaded project (if any)

    project = STORAGE_CLIENT.get_project(args["id"])
    project_sources = STORAGE_CLIENT.get_project_sources(args["id"])

    script_path = os.path.join(PROJECT_PATH, "script.py")

    # TODO just write out all in sources?
    async with aiofiles.open(script_path, "w") as f:
        await f.write(project_sources.script)
    make_executable(script_path)

    async with aiofiles.open(os.path.join(PROJECT_PATH, "resources.py"), "w") as f:
        await f.write(project_sources.resources)

    scene = STORAGE_CLIENT.get_scene(project.scene_id)

    objects_path = os.path.join(PROJECT_PATH, "object_types")

    if not os.path.exists(objects_path):
        os.makedirs(objects_path)

        async with aiofiles.open(os.path.join(objects_path, "__init__.py"), mode='w') as f:
            pass

    built_in_types = built_in_types_names()

    to_download = set()

    # in scene, there might be more instances of one type
    # ...here we will get necessary types
    for obj in scene.objects:

        # if built-in, do not attempt to find it in DB
        if obj.type in built_in_types:
            continue

        to_download.add(obj.type)

    for obj_type_name in to_download:

        obj_type = STORAGE_CLIENT.get_object_type(obj_type_name)

        async with aiofiles.open(os.path.join(objects_path, convert_cc(obj_type_name)) + ".py", "w") as f:
            await f.write(obj_type.source)

    return response(req)


async def send_to_clients(data: Dict) -> None:

    if CLIENTS:
        await asyncio.wait([client.send(json.dumps(data)) for client in CLIENTS])


async def register(websocket: WebSocketServerProtocol) -> None:

    await logger.info("Registering new client")
    CLIENTS.add(websocket)
    # TODO send current state


async def unregister(websocket: WebSocketServerProtocol) -> None:
    await logger.info("Unregistering client")
    CLIENTS.remove(websocket)

RPC_DICT: Dict[str, Callable] = {'runProject': project_run,
                                 'stopProject': project_stop,
                                 'pauseProject': project_pause,
                                 'resumeProject': project_resume,
                                 'loadProject': project_load}


def main() -> None:

    assert sys.version_info >= (3, 6)

    parser = argparse.ArgumentParser()
    parser.add_argument('--rpc-plugins', nargs='*')

    for k, v in parser.parse_args()._get_kwargs():

        if not v:
            continue

        if k == "rpc_plugins":
            for plugin in v:
                try:
                    _, cls = import_cls(plugin)
                except ImportClsException as e:
                    print(e)
                    continue

                if not issubclass(cls, RpcPlugin):
                    print(f"{cls.__name__} not subclass of RpcPlugin, ignoring.")
                    continue

                RPC_PLUGINS.append(cls())

    bound_handler = functools.partial(server, logger=logger, register=register, unregister=unregister,
                                      rpc_dict=RPC_DICT)
    asyncio.get_event_loop().set_debug(enabled=True)
    asyncio.get_event_loop().run_until_complete(
        websockets.serve(bound_handler, '0.0.0.0', 6790))
    asyncio.get_event_loop().run_forever()


if __name__ == "__main__":
    main()
