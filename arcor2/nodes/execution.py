#!/usr/bin/env python3
# -*- coding: utf-8 -*-


import argparse
import asyncio
import base64
import functools
import json
import os
import shutil
import sys
import tempfile
import zipfile
from typing import Optional, Set, Union, Awaitable, List
from datetime import datetime, timezone

from aiorun import run  # type: ignore
import websockets
from aiologger import Logger  # type: ignore
from aiologger.levels import LogLevel  # type: ignore
from dataclasses_jsonschema import ValidationError
from websockets.server import WebSocketServerProtocol as WsClient

import arcor2
from arcor2.exceptions import Arcor2Exception
from arcor2.data import rpc, compile_json_schemas
from arcor2.data.common import PackageState, PackageStateEnum, Project
from arcor2.data.execution import PackageMeta
from arcor2.data.events import ActionStateEvent, CurrentActionEvent, Event, PackageStateEvent, PackageInfoEvent
from arcor2.data.helpers import EVENT_MAPPING
from arcor2.helpers import RPC_DICT_TYPE, aiologger_formatter, server
from arcor2.settings import PROJECT_PATH
from arcor2.source.utils import make_executable


PORT = 6790

logger = Logger.with_default_handlers(name='manager', formatter=aiologger_formatter())

PROCESS: Union[asyncio.subprocess.Process, None] = None
PROJECT_EVENT: PackageStateEvent = PackageStateEvent()
PACKAGE_INFO_EVENT: Optional[PackageInfoEvent] = None
ACTION_EVENT: Optional[ActionStateEvent] = None
ACTION_ARGS_EVENT: Optional[CurrentActionEvent] = None
TASK = None

CLIENTS: Set = set()

MAIN_SCRIPT_NAME = "script.py"


def process_running() -> bool:

    return PROCESS is not None and PROCESS.returncode is None


async def project_state(event: PackageStateEvent):

    global PROJECT_EVENT
    PROJECT_EVENT = event
    await send_to_clients(event)


async def read_proc_stdout() -> None:

    global PROJECT_EVENT
    global ACTION_EVENT
    global ACTION_ARGS_EVENT
    global PACKAGE_INFO_EVENT

    logger.info("Reading script stdout...")

    assert PROCESS is not None
    assert PROCESS.stdout is not None

    await project_state(PackageStateEvent(data=PackageState(PackageStateEnum.RUNNING)))

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

        if isinstance(evt, PackageStateEvent):
            await project_state(evt)
            continue
        elif isinstance(evt, ActionStateEvent):
            ACTION_EVENT = evt
        elif isinstance(evt, CurrentActionEvent):
            ACTION_ARGS_EVENT = evt
        elif isinstance(evt, PackageInfoEvent):
            PACKAGE_INFO_EVENT = evt

        await send_to_clients(evt)

    ACTION_EVENT = None
    ACTION_ARGS_EVENT = None
    PACKAGE_INFO_EVENT = None

    await project_state(PackageStateEvent(data=PackageState(PackageStateEnum.STOPPED)))
    logger.info(f"Process finished with returncode {PROCESS.returncode}.")


async def run_package_cb(req: rpc.execution.RunPackageRequest, ui: WsClient) -> None:

    global PROCESS
    global TASK

    if process_running():
        raise Arcor2Exception("Already running!")

    package_path = os.path.join(PROJECT_PATH, req.args.id)

    try:
        os.chdir(package_path)
    except FileNotFoundError:
        raise Arcor2Exception("Not found.")

    script_path = os.path.join(package_path, MAIN_SCRIPT_NAME)

    try:
        make_executable(script_path)
    except FileNotFoundError:
        raise Arcor2Exception("Not an execution package.")

    await logger.info(f"Starting script: {script_path}")
    PROCESS = await asyncio.create_subprocess_exec(script_path, stdin=asyncio.subprocess.PIPE,
                                                   stdout=asyncio.subprocess.PIPE,
                                                   stderr=asyncio.subprocess.STDOUT)
    if PROCESS.returncode is not None:
        raise Arcor2Exception("Failed to start project.")

    TASK = asyncio.ensure_future(read_proc_stdout())  # run task in background


async def stop_package_cb(req: rpc.execution.StopPackageRequest, ui: WsClient) -> None:

    global PACKAGE_INFO_EVENT

    if not process_running():
        raise Arcor2Exception("Project not running.")

    assert PROCESS is not None
    assert TASK is not None

    await logger.info("Terminating process")
    PROCESS.terminate()
    await logger.info("Waiting for process to finish...")
    await asyncio.wait([TASK])
    PACKAGE_INFO_EVENT = None


async def pause_package_cb(req: rpc.execution.PausePackageRequest, ui: WsClient) -> None:

    if not process_running():
        raise Arcor2Exception("Project not running.")

    assert PROCESS is not None
    assert PROCESS.stdin is not None

    if PROJECT_EVENT.data.state != PackageStateEnum.RUNNING:
        raise Arcor2Exception("Cannot pause.")

    PROCESS.stdin.write("p\n".encode())
    await PROCESS.stdin.drain()
    return None


async def resume_package_cb(req: rpc.execution.ResumePackageRequest, ui: WsClient) -> None:

    if not process_running():
        raise Arcor2Exception("Project not running.")

    assert PROCESS is not None and PROCESS.stdin is not None

    if PROJECT_EVENT.data.state != PackageStateEnum.PAUSED:
        raise Arcor2Exception("Cannot resume.")

    PROCESS.stdin.write("r\n".encode())
    await PROCESS.stdin.drain()
    return None


async def package_state_cb(req: rpc.execution.PackageStateRequest, ui: WsClient) ->\
        rpc.execution.PackageStateResponse:

    resp = rpc.execution.PackageStateResponse()
    resp.data.project = PROJECT_EVENT.data
    if ACTION_EVENT:
        resp.data.action = ACTION_EVENT.data
    if ACTION_ARGS_EVENT:
        resp.data.action_args = ACTION_ARGS_EVENT.data
    return resp


async def _upload_package_cb(req: rpc.execution.UploadPackageRequest, ui: WsClient) -> None:

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
            raise Arcor2Exception("Invalid zip file.")

        os.remove(zip_path)

        try:
            shutil.rmtree(target_path)
        except FileNotFoundError:
            pass
        shutil.copytree(tmpdirname, target_path)

    script_path = os.path.join(target_path, MAIN_SCRIPT_NAME)
    make_executable(script_path)
    return None


async def read_package_meta(package_id: str) -> PackageMeta:

    target_path = os.path.join(PROJECT_PATH, package_id, "package.json")

    try:
        with open(target_path) as pkg_file:
            return PackageMeta.from_json(pkg_file.read())
    except (IOError, ValidationError) as e:
        asyncio.ensure_future(logger.error(f"Failed to read package.json of {package_id}: {e}"))
        return PackageMeta("N/A", datetime.fromtimestamp(0, tz=timezone.utc))


async def list_packages_cb(req: rpc.execution.ListPackagesRequest, ui: WsClient) ->\
        rpc.execution.ListPackagesResponse:

    resp = rpc.execution.ListPackagesResponse()

    subfolders = [f.path for f in os.scandir(PROJECT_PATH) if f.is_dir()]

    for folder_path in subfolders:

        if not os.path.isfile(os.path.join(folder_path, MAIN_SCRIPT_NAME)):
            continue

        package_dir = os.path.basename(folder_path)

        with open(os.path.join(folder_path, "data", "project.json")) as project_file:
            try:
                project = Project.from_json(project_file.read())
            except ValidationError as e:
                await logger.error(f"Failed to parse project file of {package_dir}: {e}")
                continue

        assert project.modified

        resp.data.append(rpc.execution.PackageSummary(package_dir, project.id, project.modified,
                                                      await read_package_meta(package_dir)))

        # TODO report manual changes (check last modification of files)?

    return resp


async def delete_package_cb(req: rpc.execution.DeletePackageRequest, ui: WsClient) -> None:

    if PACKAGE_INFO_EVENT and PACKAGE_INFO_EVENT.data and PACKAGE_INFO_EVENT.data.package_id == req.args.id:
        raise Arcor2Exception("Package is being executed.")

    target_path = os.path.join(PROJECT_PATH, req.args.id)

    try:
        shutil.rmtree(target_path)
    except FileNotFoundError:
        raise Arcor2Exception("Not found.")

    return None


async def rename_package_cb(req: rpc.execution.RenamePackageRequest, ui: WsClient) -> None:

    target_path = os.path.join(PROJECT_PATH, req.args.package_id, "package.json")

    pm = await read_package_meta(req.args.package_id)
    pm.name = req.args.new_name

    with open(target_path, "w") as pkg_file:
        pkg_file.write(pm.to_json())


async def send_to_clients(event: Event) -> None:

    if CLIENTS:
        data = event.to_json()
        await asyncio.wait([client.send(data) for client in CLIENTS])


async def register(websocket: WsClient) -> None:

    await logger.info("Registering new client")
    CLIENTS.add(websocket)

    tasks: List[Awaitable] = [websocket.send(PROJECT_EVENT.to_json())]

    if PACKAGE_INFO_EVENT:
        tasks.append(websocket.send(PACKAGE_INFO_EVENT.to_json()))

    await asyncio.gather(*tasks)


async def unregister(websocket: WsClient) -> None:
    await logger.info("Unregistering client")
    CLIENTS.remove(websocket)

RPC_DICT: RPC_DICT_TYPE = {
    rpc.execution.RunPackageRequest: run_package_cb,
    rpc.execution.StopPackageRequest: stop_package_cb,
    rpc.execution.PausePackageRequest: pause_package_cb,
    rpc.execution.ResumePackageRequest: resume_package_cb,
    rpc.execution.PackageStateRequest: package_state_cb,
    rpc.execution.UploadPackageRequest: _upload_package_cb,
    rpc.execution.ListPackagesRequest: list_packages_cb,
    rpc.execution.DeletePackageRequest: delete_package_cb,
    rpc.execution.RenamePackageRequest: rename_package_cb
}


async def aio_main() -> None:

    await websockets.serve(
        functools.partial(server, logger=logger, register=register, unregister=unregister, rpc_dict=RPC_DICT),
        '0.0.0.0', PORT)


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

    compile_json_schemas()

    run(aio_main(), loop=loop, stop_on_unhandled_errors=True)


if __name__ == "__main__":
    main()
