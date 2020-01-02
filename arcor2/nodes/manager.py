#!/usr/bin/env python3
# -*- coding: utf-8 -*-


import asyncio
import json
import functools
import sys
from typing import Union, Set, Optional
import os
import tempfile
import zipfile
import shutil

import websockets
from websockets.server import WebSocketServerProtocol
from aiologger import Logger  # type: ignore
from dataclasses_jsonschema import ValidationError

from arcor2.helpers import server, aiologger_formatter, RPC_RETURN_TYPES, RPC_DICT_TYPE, run_in_executor
from arcor2.source.utils import make_executable
from arcor2.settings import PROJECT_PATH
from arcor2.data.rpc import RunProjectRequest, StopProjectRequest, StopProjectResponse, \
    PauseProjectRequest, PauseProjectResponse, ResumeProjectRequest, ResumeProjectResponse, RunProjectResponse,\
    ProjectStateRequest, ProjectStateResponse
from arcor2.data.events import Event, ProjectStateEvent, ActionStateEvent, CurrentActionEvent
from arcor2.data.common import ProjectStateEnum, ProjectState
from arcor2.data.helpers import EVENT_MAPPING
from arcor2 import rest
from arcor2.nodes import builder

BUILDER_URL = os.getenv("ARCOR2_BUILDER_URL", f"http://0.0.0.0:{builder.PORT}")

PORT = 6790

logger = Logger.with_default_handlers(name='manager', formatter=aiologger_formatter())

PROCESS: Union[asyncio.subprocess.Process, None] = None
PROJECT_EVENT: ProjectStateEvent = ProjectStateEvent()
ACTION_EVENT: Optional[ActionStateEvent] = None
ACTION_ARGS_EVENT: Optional[CurrentActionEvent] = None
PROJECT_ID: Optional[str] = None
TASK = None

CLIENTS: Set = set()


def process_running() -> bool:

    return PROCESS is not None and PROCESS.returncode is None


async def project_state(event: ProjectStateEvent):

    global PROJECT_EVENT
    PROJECT_EVENT = event
    await send_to_clients(event)


async def read_proc_stdout() -> None:

    global PROJECT_EVENT
    global ACTION_EVENT
    global ACTION_ARGS_EVENT
    global PROJECT_ID

    logger.info("Reading script stdout...")

    assert PROCESS is not None
    assert PROCESS.stdout is not None

    await project_state(ProjectStateEvent(ProjectState(ProjectStateEnum.RUNNING)))

    while process_running():
        try:
            stdout = await PROCESS.stdout.readuntil()
        except asyncio.exceptions.IncompleteReadError:
            break

        try:
            data = json.loads(stdout.decode("utf-8").strip())
        except json.decoder.JSONDecodeError as e:
            await logger.error(e)
            continue

        if "event" not in data:
            await logger.error("Strange data from script: {}".format(data))
            continue

        try:
            evt = EVENT_MAPPING[data["event"]].from_dict(data)
        except ValidationError as e:
            await logger.error("Invalid event: {}, error: {}".format(data, e))
            continue

        if isinstance(evt, ProjectStateEvent):
            await project_state(evt)
            continue
        elif isinstance(evt, ActionStateEvent):
            ACTION_EVENT = evt
        elif isinstance(evt, CurrentActionEvent):
            ACTION_ARGS_EVENT = evt

        await send_to_clients(evt)

    ACTION_EVENT = None
    ACTION_ARGS_EVENT = None
    PROJECT_ID = None

    await project_state(ProjectStateEvent(ProjectState(ProjectStateEnum.STOPPED)))

    logger.info(f"Process finished with returncode {PROCESS.returncode}.")


async def project_run(req: RunProjectRequest) -> Union[RunProjectResponse, RPC_RETURN_TYPES]:

    global PROCESS
    global TASK
    global PROJECT_ID

    if process_running():
        return False, "Already running!"

    with tempfile.TemporaryDirectory() as tmpdirname:

        path = os.path.join(tmpdirname, "publish.zip")

        try:
            await run_in_executor(rest.download, f"{BUILDER_URL}/project/{req.args.id}/publish", path)
        except rest.RestException as e:
            await logger.error(e)
            return False, "Failed to get project package."

        try:
            with zipfile.ZipFile(path, 'r') as zip_ref:
                zip_ref.extractall(tmpdirname)
        except zipfile.BadZipFile as e:
            await logger.error(e)
            return False, "Invalid zip file."

        os.remove(path)

        try:
            shutil.rmtree(PROJECT_PATH)
        except FileNotFoundError:
            pass
        shutil.copytree(tmpdirname, PROJECT_PATH)

    script_path = os.path.join(PROJECT_PATH, "script.py")
    make_executable(script_path)

    path = os.path.join(PROJECT_PATH, "script.py")

    await logger.info(f"Starting script: {path}")
    PROCESS = await asyncio.create_subprocess_exec(path, stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
                                                   stderr=asyncio.subprocess.STDOUT)
    if PROCESS.returncode is not None:
        return False, "Failed to start project."
    PROJECT_ID = req.args.id
    TASK = asyncio.ensure_future(read_proc_stdout())  # run task in background


async def project_stop(req: StopProjectRequest) -> Union[StopProjectResponse, RPC_RETURN_TYPES]:

    if not process_running():
        return False, "Project not running."

    assert PROCESS is not None
    assert TASK is not None

    await logger.info("Terminating process")
    PROCESS.terminate()
    await logger.info("Waiting for process to finish...")
    await asyncio.wait([TASK])


async def project_pause(req: PauseProjectRequest) -> Union[PauseProjectResponse, RPC_RETURN_TYPES]:

    if not process_running():
        return False, "Project not running."

    assert PROCESS is not None
    assert PROCESS.stdin is not None

    if PROJECT_EVENT.data.state != ProjectStateEnum.RUNNING:
        return False, "Cannot pause."

    PROCESS.stdin.write("p\n".encode())
    await PROCESS.stdin.drain()
    return None


async def project_resume(req: ResumeProjectRequest) -> Union[ResumeProjectResponse, RPC_RETURN_TYPES]:

    if not process_running():
        return False, "Project not running."

    assert PROCESS is not None and PROCESS.stdin is not None

    if PROJECT_EVENT.data.state != ProjectStateEnum.PAUSED:
        return False, "Cannot resume."

    PROCESS.stdin.write("r\n".encode())
    await PROCESS.stdin.drain()
    return None


async def project_state_cb(req: ProjectStateRequest) -> Union[ProjectStateResponse, RPC_RETURN_TYPES]:

    resp = ProjectStateResponse()
    resp.data.project = PROJECT_EVENT.data
    if ACTION_EVENT:
        resp.data.action = ACTION_EVENT.data
    if ACTION_ARGS_EVENT:
        resp.data.action_args = ACTION_ARGS_EVENT.data
    resp.data.id = PROJECT_ID
    return resp


async def send_to_clients(event: Event) -> None:

    if CLIENTS:
        data = event.to_json()
        await asyncio.wait([client.send(data) for client in CLIENTS])


async def register(websocket: WebSocketServerProtocol) -> None:

    await logger.info("Registering new client")
    CLIENTS.add(websocket)
    # TODO send current state


async def unregister(websocket: WebSocketServerProtocol) -> None:
    await logger.info("Unregistering client")
    CLIENTS.remove(websocket)

RPC_DICT: RPC_DICT_TYPE = {
    RunProjectRequest: project_run,
    StopProjectRequest: project_stop,
    PauseProjectRequest: project_pause,
    ResumeProjectRequest: project_resume,
    ProjectStateRequest: project_state_cb
}


def main() -> None:

    assert sys.version_info >= (3, 8)

    bound_handler = functools.partial(server, logger=logger, register=register, unregister=unregister,
                                      rpc_dict=RPC_DICT)
    asyncio.get_event_loop().set_debug(enabled=True)
    asyncio.get_event_loop().run_until_complete(
        websockets.serve(bound_handler, '0.0.0.0', PORT))
    asyncio.get_event_loop().run_forever()


if __name__ == "__main__":
    main()
