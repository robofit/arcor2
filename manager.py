#!/usr/bin/env python3
# -*- coding: utf-8 -*-


import asyncio
import json
import websockets
import functools
import sys
from typing import Dict, List, Union, Set, Optional
import arcor2.core
import arcor2.user_objects
import arcor2.projects
from aiologger import Logger
import motor.motor_asyncio
import os
import arcor2.projects


logger = Logger.with_default_handlers(name='arcor2-manager')

PROJECT = "demo_v0"
PROCESS: Union[asyncio.subprocess.Process, None] = None
TASK = None

CLIENTS: Set = set()

mongo = motor.motor_asyncio.AsyncIOMotorClient()


def rpc(f):
    async def wrapper(req, ui, args, req_id):

        msg = await f(req, ui, args, req_id)
        j = json.dumps(msg)
        await asyncio.wait([ui.send(j)])
        await logger.debug("RPC request: {}, args: {}, req_id: {}, result: {}".format(req, args, req_id, j))

    return wrapper


def process_running() -> bool:

    return PROCESS and PROCESS.returncode is None


def response(resp_to: str, req_id: int, result: bool = True, messages: Optional[List[str]] = None) -> Dict:

    if messages is None:
        messages = []

    return {"response": resp_to, "req_id": req_id, "result": result, "messages": messages}


async def read_proc_stdout():

    logger.info("Reading script stdout...")

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

    logger.info("Process finished with returncode {}.".format(PROCESS.returncode))


@rpc
async def project_run(req, client, args, req_id) -> Dict:

    global PROCESS
    global TASK

    if process_running():
        return response(req, req_id, False, ["Already running!"])

    path = os.path.join(arcor2.projects.__path__[0], PROJECT, "script.py")

    await logger.info("Starting script: {}".format(path))
    PROCESS = await asyncio.create_subprocess_exec(path, stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
                                                    stderr=asyncio.subprocess.STDOUT)
    if PROCESS.returncode is None:
        TASK = asyncio.ensure_future(read_proc_stdout())  # run task in background
        return response(req, req_id)
    else:
        return response(req, req_id, False, ["Failed to start project."])

@rpc
async def project_stop(req, client, args, req_id) -> Dict:

    if not process_running():
        return response(req, req_id, False, ["Project not running."])

    await logger.info("Terminating process")

    # TODO send "s" and wait for script to stop itself
    # PROCESS.stdin.write("s\n")
    PROCESS.terminate()
    await logger.info("Waiting for process to finish...")
    # await PROCESS.wait()
    await TASK
    return response(req, req_id)

@rpc
async def project_pause(req, client, args, req_id) -> Dict:

    if not process_running():
        return response(req, req_id, False, ["Project not running."])

    # TODO check if it is not already paused

    PROCESS.stdin.write("p\n".encode())
    await PROCESS.stdin.drain()
    return response(req, req_id)


@rpc
async def project_resume(req, client, args, req_id) -> Dict:

    if not process_running():
        return response(req, req_id, False, ["Project not running."])

    # TODO check if paused

    PROCESS.stdin.write("r\n".encode())
    await PROCESS.stdin.drain()
    return response(req, req_id)


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

RPC_DICT: Dict = {'runProject': project_run,
                  'stopProject': project_stop,
                  'pauseProject': project_pause,
                  'resumeProject': project_resume}


async def server(client, path, extra_argument) -> None:

    await register(client)
    try:
        async for message in client:

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

                await rpc_func(data['request'], client, data.get("args", {}), data.get("req_id", 0))
            else:
                await logger.error("unsupported format of message: {}".format(data))
    finally:
        await unregister(client)


def main():

    assert sys.version_info >= (3, 6)

    bound_handler = functools.partial(server, extra_argument='spam')
    asyncio.get_event_loop().set_debug(enabled=True)
    asyncio.get_event_loop().run_until_complete(
        websockets.serve(bound_handler, '0.0.0.0', 6790))
    asyncio.get_event_loop().run_forever()


if __name__ == "__main__":
    main()
