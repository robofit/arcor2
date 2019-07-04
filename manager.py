#!/usr/bin/env python3
# -*- coding: utf-8 -*-


import asyncio
import json
import websockets  # type: ignore
import functools
import sys
from typing import Dict, Union, Set, Callable, Optional
import arcor2.core
import arcor2.user_objects
import arcor2.projects
from aiologger import Logger  # type: ignore
import motor.motor_asyncio  # type: ignore
import os
from arcor2.helpers import response, rpc, server


logger = Logger.with_default_handlers(name='arcor2-manager')

PROJECT: str = "demo_v0"
PROCESS: Union[asyncio.subprocess.Process, None] = None
TASK = None

CLIENTS: Set = set()

mongo = motor.motor_asyncio.AsyncIOMotorClient()


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


@rpc(logger)
async def project_run(req: str, client, args: Dict) -> Dict:

    global PROCESS
    global TASK

    if process_running():
        return response(req, False, ["Already running!"])

    path = os.path.join(arcor2.projects.__path__[0], PROJECT, "script.py")

    await logger.info(f"Starting script: {path}")
    PROCESS = await asyncio.create_subprocess_exec(path, stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
                                                   stderr=asyncio.subprocess.STDOUT)
    if PROCESS.returncode is None:
        TASK = asyncio.ensure_future(read_proc_stdout())  # run task in background
        return response(req)
    else:
        return response(req, False, ["Failed to start project."])


@rpc(logger)
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


@rpc(logger)
async def project_pause(req: str, client, args: Dict) -> Dict:

    if not process_running():
        return response(req, False, ["Project not running."])

    assert PROCESS is not None
    assert PROCESS.stdin is not None

    # TODO check if it is not already paused

    PROCESS.stdin.write("p\n".encode())
    await PROCESS.stdin.drain()
    return response(req)


@rpc(logger)
async def project_resume(req: str, client, args: Dict) -> Dict:

    if not process_running():
        return response(req, False, ["Project not running."])

    assert PROCESS is not None and PROCESS.stdin is not None

    # TODO check if paused

    PROCESS.stdin.write("r\n".encode())
    await PROCESS.stdin.drain()
    return response(req)


async def send_to_clients(data: Dict) -> None:

    if CLIENTS:
        await asyncio.wait([client.send(json.dumps(data)) for client in CLIENTS])


async def register(websocket) -> None:
    await logger.info("Registering new client")
    CLIENTS.add(websocket)
    # TODO send current state


async def unregister(websocket) -> None:
    await logger.info("Unregistering client")
    CLIENTS.remove(websocket)

RPC_DICT: Dict[str, Callable] = {'runProject': project_run,
                                 'stopProject': project_stop,
                                 'pauseProject': project_pause,
                                 'resumeProject': project_resume}


def main():

    assert sys.version_info >= (3, 6)

    bound_handler = functools.partial(server, logger=logger, register=register, unregister=unregister,
                                      rpc_dict=RPC_DICT)
    asyncio.get_event_loop().set_debug(enabled=True)
    asyncio.get_event_loop().run_until_complete(
        websockets.serve(bound_handler, '0.0.0.0', 6790))
    asyncio.get_event_loop().run_forever()


if __name__ == "__main__":
    main()
