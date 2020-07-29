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
import time
import zipfile
from datetime import datetime, timezone
from typing import Awaitable, List, Optional, Set, Union

from aiologger import Logger  # type: ignore
from aiologger.levels import LogLevel  # type: ignore

from aiorun import run  # type: ignore

from dataclasses_jsonschema import ValidationError

import websockets
from websockets.server import WebSocketServerProtocol as WsClient

import arcor2
from arcor2.data import common, compile_json_schemas, events, rpc
from arcor2.data.execution import PackageSummary
from arcor2.data.helpers import EVENT_MAPPING
from arcor2.exceptions import Arcor2Exception
from arcor2.helpers import RPC_DICT_TYPE, aiologger_formatter, read_package_meta, server, write_package_meta
from arcor2.settings import PROJECT_PATH
from arcor2.source.utils import make_executable

PORT = 6790

logger = Logger.with_default_handlers(name='Execution', formatter=aiologger_formatter())

PROCESS: Union[asyncio.subprocess.Process, None] = None
PACKAGE_STATE_EVENT = events.PackageStateEvent()
RUNNING_PACKAGE_ID: Optional[str] = None
PACKAGE_INFO_EVENT: Optional[events.PackageInfoEvent] = None  # in case of man. written scripts, this might not be sent
ACTION_EVENT: Optional[events.ActionStateEvent] = None
ACTION_ARGS_EVENT: Optional[events.CurrentActionEvent] = None
TASK = None

CLIENTS: Set = set()

MAIN_SCRIPT_NAME = "script.py"


def process_running() -> bool:

    return PROCESS is not None and PROCESS.returncode is None


async def package_state(event: events.PackageStateEvent):

    global PACKAGE_STATE_EVENT
    PACKAGE_STATE_EVENT = event
    await send_to_clients(event)


async def read_proc_stdout() -> None:

    global PACKAGE_STATE_EVENT
    global ACTION_EVENT
    global ACTION_ARGS_EVENT
    global PACKAGE_INFO_EVENT
    global RUNNING_PACKAGE_ID

    logger.info("Reading script stdout...")

    assert PROCESS is not None
    assert PROCESS.stdout is not None
    assert RUNNING_PACKAGE_ID is not None

    await package_state(
        events.PackageStateEvent(
            data=common.PackageState(common.PackageStateEnum.RUNNING, RUNNING_PACKAGE_ID)
        )
    )

    printed_out: List[str] = []

    while process_running():
        try:
            stdout = await PROCESS.stdout.readuntil()
        except asyncio.exceptions.IncompleteReadError:
            print("break")
            break

        decoded = stdout.decode("utf-8")
        stripped = decoded.strip()

        try:
            data = json.loads(stripped)
        except json.decoder.JSONDecodeError:
            printed_out.append(decoded)
            logger.error(decoded.strip())
            continue

        if not isinstance(data, dict) or "event" not in data:
            logger.error("Strange data from script: {}".format(data))
            continue

        try:
            evt = EVENT_MAPPING[data["event"]].from_dict(data)
        except ValidationError as e:
            logger.error("Invalid event: {}, error: {}".format(data, e))
            continue

        if isinstance(evt, events.PackageStateEvent):
            evt.data.package_id = RUNNING_PACKAGE_ID
            await package_state(evt)
            continue
        elif isinstance(evt, events.ActionStateEvent):
            ACTION_EVENT = evt
        elif isinstance(evt, events.CurrentActionEvent):
            ACTION_ARGS_EVENT = evt
        elif isinstance(evt, events.PackageInfoEvent):
            PACKAGE_INFO_EVENT = evt

        await send_to_clients(evt)

    ACTION_EVENT = None
    ACTION_ARGS_EVENT = None
    PACKAGE_INFO_EVENT = None

    if PROCESS.returncode:

        if printed_out:

            # TODO remember this (until another package is started) and send it to new clients?
            await send_to_clients(
                events.ProjectExceptionEvent(
                    data=events.ProjectExceptionEventData(printed_out[-1].strip())
                )
            )

            with open("traceback-{}.txt".format(time.strftime("%Y%m%d-%H%M%S")), "w") as tb_file:
                tb_file.write("".join(printed_out))

        else:
            logger.warn(
                f"Process ended with non-zero return code ({PROCESS.returncode}), but didn't printed out anything.")

    await package_state(
        events.PackageStateEvent(
            data=common.PackageState(common.PackageStateEnum.STOPPED, RUNNING_PACKAGE_ID)
        )
    )
    logger.info(f"Process finished with returncode {PROCESS.returncode}.")

    RUNNING_PACKAGE_ID = None


async def run_package_cb(req: rpc.execution.RunPackageRequest, ui: WsClient) -> None:

    global PROCESS
    global TASK
    global RUNNING_PACKAGE_ID

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

    logger.info(f"Starting script: {script_path}")
    PROCESS = await asyncio.create_subprocess_exec(script_path, stdin=asyncio.subprocess.PIPE,
                                                   stdout=asyncio.subprocess.PIPE,
                                                   stderr=asyncio.subprocess.STDOUT)
    if PROCESS.returncode is not None:
        raise Arcor2Exception("Failed to start project.")

    meta = read_package_meta(req.args.id)
    meta.executed = datetime.now(tz=timezone.utc)
    write_package_meta(req.args.id, meta)

    RUNNING_PACKAGE_ID = req.args.id

    TASK = asyncio.ensure_future(read_proc_stdout())  # run task in background


async def stop_package_cb(req: rpc.execution.StopPackageRequest, ui: WsClient) -> None:

    global PACKAGE_INFO_EVENT
    global RUNNING_PACKAGE_ID

    if not process_running():
        raise Arcor2Exception("Project not running.")

    assert PROCESS is not None
    assert TASK is not None

    logger.info("Terminating process")
    PROCESS.terminate()
    logger.info("Waiting for process to finish...")
    await asyncio.wait([TASK])
    PACKAGE_INFO_EVENT = None
    RUNNING_PACKAGE_ID = None


async def pause_package_cb(req: rpc.execution.PausePackageRequest, ui: WsClient) -> None:

    if not process_running():
        raise Arcor2Exception("Project not running.")

    assert PROCESS is not None
    assert PROCESS.stdin is not None

    if PACKAGE_STATE_EVENT.data.state != common.PackageStateEnum.RUNNING:
        raise Arcor2Exception("Cannot pause.")

    PROCESS.stdin.write("p\n".encode())
    await PROCESS.stdin.drain()
    return None


async def resume_package_cb(req: rpc.execution.ResumePackageRequest, ui: WsClient) -> None:

    if not process_running():
        raise Arcor2Exception("Project not running.")

    assert PROCESS is not None
    assert PROCESS.stdin is not None

    if PACKAGE_STATE_EVENT.data.state != common.PackageStateEnum.PAUSED:
        raise Arcor2Exception("Cannot resume.")

    PROCESS.stdin.write("r\n".encode())
    await PROCESS.stdin.drain()
    return None


async def package_state_cb(req: rpc.execution.PackageStateRequest, ui: WsClient) ->\
        rpc.execution.PackageStateResponse:

    resp = rpc.execution.PackageStateResponse()
    resp.data.project = PACKAGE_STATE_EVENT.data
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
            logger.error(e)
            raise Arcor2Exception("Invalid zip file.")

        os.remove(zip_path)

        try:
            shutil.rmtree(target_path)
        except FileNotFoundError:
            pass
        shutil.copytree(tmpdirname, target_path)

    script_path = os.path.join(target_path, MAIN_SCRIPT_NAME)

    try:
        make_executable(script_path)
    except FileNotFoundError:
        raise Arcor2Exception("Package does not contain 'script.py' file.")

    asyncio.ensure_future(
        send_to_clients(
            events.PackageChanged(events.EventType.ADD, data=await get_summary(target_path))
        )
    )
    return None


async def get_summary(path: str) -> PackageSummary:

    if not os.path.isfile(os.path.join(path, MAIN_SCRIPT_NAME)):
        raise Arcor2Exception("Package does not contain main script.")

    package_dir = os.path.basename(path)
    package_meta = read_package_meta(package_dir)

    try:
        with open(os.path.join(path, "data", "project.json")) as project_file:
            project = common.Project.from_json(project_file.read())
    except (ValidationError, IOError) as e:
        logger.error(f"Failed to read/parse project file of {package_dir}: {e}")

        return PackageSummary(package_dir, "N/A", datetime.fromtimestamp(0, tz=timezone.utc), package_meta)

    assert project.modified
    return PackageSummary(package_dir, project.id, project.modified, package_meta)


async def list_packages_cb(req: rpc.execution.ListPackagesRequest, ui: WsClient) ->\
        rpc.execution.ListPackagesResponse:

    resp = rpc.execution.ListPackagesResponse()

    subfolders = [f.path for f in os.scandir(PROJECT_PATH) if f.is_dir()]

    for folder_path in subfolders:

        try:
            resp.data.append(await get_summary(folder_path))
        except Arcor2Exception:
            pass

    return resp


async def delete_package_cb(req: rpc.execution.DeletePackageRequest, ui: WsClient) -> None:

    if RUNNING_PACKAGE_ID and RUNNING_PACKAGE_ID == req.args.id:
        raise Arcor2Exception("Package is being executed.")

    target_path = os.path.join(PROJECT_PATH, req.args.id)
    package_summary = await get_summary(target_path)

    try:
        shutil.rmtree(target_path)
    except FileNotFoundError:
        raise Arcor2Exception("Not found.")

    asyncio.ensure_future(send_to_clients(events.PackageChanged(events.EventType.REMOVE, data=package_summary)))
    return None


async def rename_package_cb(req: rpc.execution.RenamePackageRequest, ui: WsClient) -> None:

    target_path = os.path.join(PROJECT_PATH, req.args.package_id, "package.json")

    pm = read_package_meta(req.args.package_id)
    pm.name = req.args.new_name

    with open(target_path, "w") as pkg_file:
        pkg_file.write(pm.to_json())

    asyncio.ensure_future(
        send_to_clients(
            events.PackageChanged(events.EventType.UPDATE,
                                  data=await get_summary(os.path.join(PROJECT_PATH, req.args.package_id)))
        )
    )


async def _version_cb(req: rpc.common.VersionRequest, ui: WsClient) -> rpc.common.VersionResponse:
    return rpc.common.VersionResponse(data=rpc.common.VersionData(arcor2.api_version()))


async def send_to_clients(event: events.Event) -> None:

    if CLIENTS:
        data = event.to_json()
        await asyncio.wait([client.send(data) for client in CLIENTS])


async def register(websocket: WsClient) -> None:

    logger.info("Registering new client")
    CLIENTS.add(websocket)

    tasks: List[Awaitable] = [websocket.send(PACKAGE_STATE_EVENT.to_json())]

    if PACKAGE_INFO_EVENT:
        tasks.append(websocket.send(PACKAGE_INFO_EVENT.to_json()))

    await asyncio.gather(*tasks)


async def unregister(websocket: WsClient) -> None:
    logger.info("Unregistering client")
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
    rpc.execution.RenamePackageRequest: rename_package_cb,
    rpc.common.VersionRequest: _version_cb
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
