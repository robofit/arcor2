#!/usr/bin/env python3
# -*- coding: utf-8 -*-


import asyncio
import json
import functools
import sys
from typing import Union, Set, Optional
import os
import argparse
import tempfile
import base64
import zipfile
import shutil

import websockets
from websockets.server import WebSocketServerProtocol
from aiologger import Logger  # type: ignore
from aiologger.levels import LogLevel  # type: ignore
from dataclasses_jsonschema import ValidationError

import arcor2
from arcor2.helpers import server, aiologger_formatter, RPC_RETURN_TYPES, RPC_DICT_TYPE
from arcor2.source.utils import make_executable
from arcor2.settings import PROJECT_PATH
from arcor2.data import rpc
from arcor2.data.events import Event, ProjectStateEvent, ActionStateEvent, CurrentActionEvent
from arcor2.data.common import ProjectStateEnum, ProjectState
from arcor2.data.helpers import EVENT_MAPPING

PORT = 6790

logger = Logger.with_default_handlers(name='manager', formatter=aiologger_formatter())

PROCESS: Union[asyncio.subprocess.Process, None] = None
PROJECT_EVENT: ProjectStateEvent = ProjectStateEvent()
ACTION_EVENT: Optional[ActionStateEvent] = None
ACTION_ARGS_EVENT: Optional[CurrentActionEvent] = None
PROJECT_ID: Optional[str] = None
TASK = None

CLIENTS: Set = set()

MAIN_SCRIPT_NAME = "script.py"


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

        stripped = stdout.decode("utf-8").strip()

        try:
            data = json.loads(stripped)
        except json.decoder.JSONDecodeError as e:
            await logger.error(f"Script printed out: {stripped}")
            await logger.debug(e)
            continue

        if not isinstance(data, dict) or "event" not in data:
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


async def project_run(req: rpc.execution.RunProjectRequest) -> Union[rpc.execution.RunProjectResponse,
                                                                     RPC_RETURN_TYPES]:

    global PROCESS
    global TASK
    global PROJECT_ID

    if process_running():
        return False, "Already running!"

    package_path = os.path.join(PROJECT_PATH, req.args.id)

    try:
        os.chdir(package_path)
    except FileNotFoundError:
        return False, "Not found."

    script_path = os.path.join(package_path, MAIN_SCRIPT_NAME)

    try:
        make_executable(script_path)
    except FileNotFoundError:
        return False, "Not an execution package."

    await logger.info(f"Starting script: {script_path}")
    PROCESS = await asyncio.create_subprocess_exec(script_path, stdin=asyncio.subprocess.PIPE,
                                                   stdout=asyncio.subprocess.PIPE,
                                                   stderr=asyncio.subprocess.STDOUT)
    if PROCESS.returncode is not None:
        return False, "Failed to start project."
    PROJECT_ID = req.args.id
    TASK = asyncio.ensure_future(read_proc_stdout())  # run task in background


async def project_stop(req: rpc.execution.StopProjectRequest) -> Union[rpc.execution.StopProjectResponse,
                                                                       RPC_RETURN_TYPES]:

    if not process_running():
        return False, "Project not running."

    assert PROCESS is not None
    assert TASK is not None

    await logger.info("Terminating process")
    PROCESS.terminate()
    await logger.info("Waiting for process to finish...")
    await asyncio.wait([TASK])


async def project_pause(req: rpc.execution.PauseProjectRequest) -> Union[rpc.execution.PauseProjectResponse,
                                                                         RPC_RETURN_TYPES]:

    if not process_running():
        return False, "Project not running."

    assert PROCESS is not None
    assert PROCESS.stdin is not None

    if PROJECT_EVENT.data.state != ProjectStateEnum.RUNNING:
        return False, "Cannot pause."

    PROCESS.stdin.write("p\n".encode())
    await PROCESS.stdin.drain()
    return None


async def project_resume(req: rpc.execution.ResumeProjectRequest) -> Union[rpc.execution.ResumeProjectResponse,
                                                                           RPC_RETURN_TYPES]:

    if not process_running():
        return False, "Project not running."

    assert PROCESS is not None and PROCESS.stdin is not None

    if PROJECT_EVENT.data.state != ProjectStateEnum.PAUSED:
        return False, "Cannot resume."

    PROCESS.stdin.write("r\n".encode())
    await PROCESS.stdin.drain()
    return None


async def project_state_cb(req: rpc.execution.ProjectStateRequest) -> Union[rpc.execution.ProjectStateResponse,
                                                                            RPC_RETURN_TYPES]:

    resp = rpc.execution.ProjectStateResponse()
    resp.data.project = PROJECT_EVENT.data
    if ACTION_EVENT:
        resp.data.action = ACTION_EVENT.data
    if ACTION_ARGS_EVENT:
        resp.data.action_args = ACTION_ARGS_EVENT.data
    resp.data.id = PROJECT_ID
    return resp


async def _upload_package_cb(req: rpc.execution.UploadPackageRequest) -> Union[rpc.execution.UploadPackageResponse,
                                                                               RPC_RETURN_TYPES]:

    target_path = os.path.join(PROJECT_PATH, req.args.id)

    # TODO do not allow if there are manual changes?

    with tempfile.TemporaryDirectory() as tmpdirname:

        zip_path = os.path.join(tmpdirname, "publish.zip")

        b64_bytes = req.args.data.encode()
        zip_content = base64.b64decode(b64_bytes)

        with open(zip_path, "wb") as zip_file:
            zip_file.write(zip_content)

        try:
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(tmpdirname)
        except zipfile.BadZipFile as e:
            await logger.error(e)
            return False, "Invalid zip file."

        os.remove(zip_path)

        try:
            shutil.rmtree(target_path)
        except FileNotFoundError:
            pass
        shutil.copytree(tmpdirname, target_path)

    script_path = os.path.join(target_path, MAIN_SCRIPT_NAME)
    make_executable(script_path)
    return None


async def list_packages_cb(req: rpc.execution.ListPackagesRequest) -> Union[rpc.execution.ListPackagesResponse,
                                                                            RPC_RETURN_TYPES]:

    resp = rpc.execution.ListPackagesResponse()

    subfolders = [f.path for f in os.scandir(PROJECT_PATH) if f.is_dir()]

    from datetime import datetime, timedelta, timezone

    for folder_path in subfolders:

        if not os.path.isfile(os.path.join(folder_path, MAIN_SCRIPT_NAME)):
            continue

        # TODO read actual project timestamp from data/project.json
        resp.data.append(rpc.execution.PackageSummary(os.path.basename(folder_path),
                                                      datetime.now(timezone.utc) - timedelta(hours=1)))

        # TODO report manual changes (check last modification of files)?

    return resp


async def delete_package_cb(req: rpc.execution.DeletePackageRequest) -> Union[rpc.execution.DeletePackageResponse,
                                                                              RPC_RETURN_TYPES]:

    if PROJECT_ID and PROJECT_ID == req.args.id:
        return False, "Package is being executed."

    target_path = os.path.join(PROJECT_PATH, req.args.id)

    try:
        shutil.rmtree(target_path)
    except FileNotFoundError:
        return False, "Not found."

    return None


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
    rpc.execution.RunProjectRequest: project_run,
    rpc.execution.StopProjectRequest: project_stop,
    rpc.execution.PauseProjectRequest: project_pause,
    rpc.execution.ResumeProjectRequest: project_resume,
    rpc.execution.ProjectStateRequest: project_state_cb,
    rpc.execution.UploadPackageRequest: _upload_package_cb,
    rpc.execution.ListPackagesRequest: list_packages_cb,
    rpc.execution.DeletePackageRequest: delete_package_cb
}


def main() -> None:

    assert sys.version_info >= (3, 8)

    parser = argparse.ArgumentParser()

    parser.add_argument("-v", "--verbose", help="Increase output verbosity",
                        action="store_const", const=LogLevel.DEBUG, default=LogLevel.INFO)
    parser.add_argument('--version', action='version', version=arcor2.version(),
                        help="Shows ARCOR2 version and exits.")
    parser.add_argument('--api_version', action='version', version=arcor2.api_version(),
                        help="Shows API version and exits.")
    parser.add_argument("-a", "--asyncio_debug", help="Turn on asyncio debug mode.",
                        action="store_const", const=True, default=False)

    args = parser.parse_args()
    logger.level = args.verbose

    loop = asyncio.get_event_loop()
    loop.set_debug(enabled=args.asyncio_debug)

    bound_handler = functools.partial(server, logger=logger, register=register, unregister=unregister,
                                      rpc_dict=RPC_DICT)
    loop.run_until_complete(
        websockets.serve(bound_handler, '0.0.0.0', PORT))
    loop.run_forever()


if __name__ == "__main__":
    main()
