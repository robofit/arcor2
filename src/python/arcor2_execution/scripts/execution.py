import argparse
import asyncio
import base64
import functools
import os
import shutil
import signal
import sys
import time
import zipfile
from datetime import datetime, timezone
from typing import Awaitable

import aiofiles
import aiofiles.os
import websockets
from aiofiles import tempfile
from aiologger.levels import LogLevel
from aiorun import run
from dataclasses_jsonschema import ValidationError
from websockets.server import WebSocketServerProtocol as WsClient

import arcor2_execution
import arcor2_execution_data
from arcor2 import env, json, ws_server
from arcor2.data import common, compile_json_schemas
from arcor2.data import rpc as arcor2_rpc
from arcor2.data.events import Event, PackageInfo, PackageState, ProjectException
from arcor2.exceptions import Arcor2Exception
from arcor2.helpers import port_from_url, run_in_executor
from arcor2.logging import get_aiologger
from arcor2_execution_data import EVENTS, URL, events, rpc
from arcor2_execution_data.common import PackageSummary, ProjectMeta
from arcor2_runtime.package import PROJECT_PATH, read_package_meta, write_package_meta

logger = get_aiologger("Execution")

PROCESS: asyncio.subprocess.Process | None = None
PACKAGE_STATE_EVENT: PackageState = PackageState(PackageState.Data())  # undefined state
RUNNING_PACKAGE_ID: None | str = None

# in case of man. written scripts, this might not be sent
PACKAGE_INFO_EVENT: None | PackageInfo = None

TASK: None | asyncio.Task = None

CLIENTS: set[WsClient] = set()

MAIN_SCRIPT_NAME = "script.py"

EVENT_MAPPING = {evt.__name__: evt for evt in EVENTS}


def process_running() -> bool:

    return PROCESS is not None and PROCESS.returncode is None


async def package_state(event: PackageState) -> None:

    PACKAGE_STATE_EVENT.data = event.data
    await send_to_clients(event)


async def read_proc_stdout() -> None:

    global PACKAGE_INFO_EVENT
    global RUNNING_PACKAGE_ID

    logger.info("Reading script stdout...")

    assert PROCESS is not None
    assert PROCESS.stdout is not None
    assert RUNNING_PACKAGE_ID is not None

    printed_out: list[str] = []

    while process_running():
        try:
            stdout = await PROCESS.stdout.readuntil()
        except asyncio.exceptions.IncompleteReadError:
            break

        decoded = stdout.decode("utf-8")
        stripped = decoded.strip()

        try:
            data = json.loads(stripped)
        except json.JsonException:
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

        if isinstance(evt, PackageState):
            evt.data.package_id = RUNNING_PACKAGE_ID
            await package_state(evt)
            continue
        elif isinstance(evt, PackageInfo):
            PACKAGE_INFO_EVENT = evt

        await send_to_clients(evt)

    PACKAGE_INFO_EVENT = None

    await PROCESS.communicate()  # otherwise returncode might be still None

    if PROCESS.returncode:

        if printed_out:

            # TODO remember this (until another package is started) and send it to new clients?
            last_line = printed_out[-1].strip()

            try:
                exception_type, message = last_line.split(":", 1)
            except ValueError:
                exception_type, message = "Unknown", last_line

            await send_to_clients(ProjectException(ProjectException.Data(message, exception_type)))

            async with aiofiles.open("traceback-{}.txt".format(time.strftime("%Y%m%d-%H%M%S")), "w") as tb_file:
                await tb_file.write("".join(printed_out))

        else:

            await send_to_clients(
                ProjectException(
                    ProjectException.Data(f"Process ended with non-zero return code ({PROCESS.returncode}).", "unknown")
                )
            )

            logger.warn(
                f"Process ended with non-zero return code ({PROCESS.returncode}), but didn't printed out anything."
            )

    await package_state(PackageState(PackageState.Data(PackageState.Data.StateEnum.STOPPED, RUNNING_PACKAGE_ID)))
    logger.info(f"Process finished with returncode {PROCESS.returncode}.")

    RUNNING_PACKAGE_ID = None


async def check_script(script_path: str) -> None:

    if not await run_in_executor(os.path.exists, script_path):
        raise Arcor2Exception("Main script not found.")


async def run_package_cb(req: rpc.RunPackage.Request, ui: WsClient) -> None:
    async def _update_executed(package_id: str) -> None:

        meta = await run_in_executor(read_package_meta, package_id)
        meta.executed = datetime.now(tz=timezone.utc)
        await run_in_executor(write_package_meta, package_id, meta)

    global PROCESS
    global TASK
    global RUNNING_PACKAGE_ID

    if PACKAGE_STATE_EVENT.data.state not in PackageState.RUNNABLE_STATES:
        raise Arcor2Exception("Package not stopped!")

    assert not process_running()

    package_path = os.path.join(PROJECT_PATH, req.args.id)

    try:
        await run_in_executor(os.chdir, package_path, propagate=[FileNotFoundError])
    except FileNotFoundError:
        raise Arcor2Exception("Not found.")

    script_path = os.path.join(package_path, MAIN_SCRIPT_NAME)
    await check_script(script_path)

    # this is necessary in order to make PEX embedded modules available to subprocess
    pypath = ":".join(sys.path)

    # create a temp copy of the env variables
    myenv = os.environ.copy()

    # set PYTHONPATH to match this scripts sys.path
    myenv["PYTHONPATH"] = pypath

    args = [script_path]

    if req.args.start_paused:
        args.append("-p")

    if req.args.breakpoints:
        args.append(f"-b \"{','.join(req.args.breakpoints)}\"")

    logger.info(f"Starting script: {script_path}")
    PROCESS = await asyncio.create_subprocess_exec(
        "python3.10",
        *args,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
        env=myenv,
    )
    if PROCESS.returncode is not None:
        raise Arcor2Exception("Failed to start package.")

    RUNNING_PACKAGE_ID = req.args.id
    await package_state(PackageState(PackageState.Data(PackageState.Data.StateEnum.RUNNING, RUNNING_PACKAGE_ID)))

    TASK = asyncio.create_task(read_proc_stdout())  # run task in background
    asyncio.create_task(_update_executed(req.args.id))


async def stop_package_cb(req: rpc.StopPackage.Request, ui: WsClient) -> None:
    async def _terminate_task() -> None:

        global PACKAGE_INFO_EVENT
        global RUNNING_PACKAGE_ID

        assert PROCESS
        assert TASK

        logger.info("Terminating process")
        PROCESS.send_signal(signal.SIGINT)  # the same as when a user presses ctrl+c

        logger.info("Waiting for process to finish...")
        await asyncio.wait([TASK])
        PACKAGE_INFO_EVENT = None
        RUNNING_PACKAGE_ID = None

    if PACKAGE_STATE_EVENT.data.state not in PackageState.RUN_STATES:
        raise Arcor2Exception("Package not running.")

    assert process_running()

    await package_state(PackageState(PackageState.Data(PackageState.Data.StateEnum.STOPPING, RUNNING_PACKAGE_ID)))
    asyncio.create_task(_terminate_task())


async def pause_package_cb(req: rpc.PausePackage.Request, ui: WsClient) -> None:
    async def _pause() -> None:

        assert PROCESS is not None
        assert PROCESS.stdin is not None

        PROCESS.stdin.write("p\n".encode())
        await PROCESS.stdin.drain()
        logger.info("Package paused.")

    if PACKAGE_STATE_EVENT.data.state != PackageState.Data.StateEnum.RUNNING:
        raise Arcor2Exception("Cannot pause.")

    await package_state(PackageState(PackageState.Data(PackageState.Data.StateEnum.PAUSING, RUNNING_PACKAGE_ID)))
    assert process_running()
    asyncio.create_task(_pause())


async def step_action_cb(req: rpc.StepAction.Request, ui: WsClient) -> None:
    async def _step() -> None:

        assert PROCESS is not None
        assert PROCESS.stdin is not None

        PROCESS.stdin.write("s\n".encode())
        await PROCESS.stdin.drain()
        logger.info("Stepping to a next action.")

    if PACKAGE_STATE_EVENT.data.state != PackageState.Data.StateEnum.PAUSED:
        raise Arcor2Exception("Can't step, execution is not paused.")

    await package_state(PackageState(PackageState.Data(PackageState.Data.StateEnum.RESUMING, RUNNING_PACKAGE_ID)))
    assert process_running()
    asyncio.create_task(_step())


async def resume_package_cb(req: rpc.ResumePackage.Request, ui: WsClient) -> None:
    async def _resume() -> None:

        assert PROCESS is not None
        assert PROCESS.stdin is not None

        PROCESS.stdin.write("r\n".encode())
        await PROCESS.stdin.drain()
        logger.info("Package resumed.")

    assert process_running()

    if PACKAGE_STATE_EVENT.data.state != PackageState.Data.StateEnum.PAUSED:
        raise Arcor2Exception("Can't resume, execution is not paused.")

    await package_state(PackageState(PackageState.Data(PackageState.Data.StateEnum.RESUMING, RUNNING_PACKAGE_ID)))
    asyncio.create_task(_resume())


async def _upload_package_cb(req: rpc.UploadPackage.Request, ui: WsClient) -> None:
    async def _upload_event(path_to_package: str) -> None:

        summary = await get_summary(path_to_package)
        evt = events.PackageChanged(summary)
        evt.change_type = Event.Type.ADD
        await send_to_clients(evt)
        logger.info(f"Package '{summary.package_meta.name}' was added.")

    target_path = os.path.join(PROJECT_PATH, req.args.id)

    # TODO do not allow if there are manual changes?

    async with tempfile.TemporaryDirectory() as tmpdirname:

        zip_path = os.path.join(tmpdirname, "publish.zip")

        b64_bytes = req.args.data.encode()
        zip_content = base64.b64decode(b64_bytes)

        async with aiofiles.open(zip_path, mode="wb") as zip_file:
            await zip_file.write(zip_content)

        try:
            with zipfile.ZipFile(zip_path, "r") as zip_ref:
                zip_ref.extractall(tmpdirname)
        except zipfile.BadZipFile as e:
            logger.error(e)
            raise Arcor2Exception("Invalid zip file.")

        await aiofiles.os.remove(zip_path)

        script_path = os.path.join(tmpdirname, MAIN_SCRIPT_NAME)
        await check_script(script_path)

        try:
            await run_in_executor(shutil.rmtree, target_path, propagate=[FileNotFoundError])
        except FileNotFoundError:
            pass
        await run_in_executor(shutil.copytree, tmpdirname, target_path)

    asyncio.create_task(_upload_event(target_path))


async def get_summary(path: str) -> PackageSummary:

    if summary := await get_opt_summary(path):
        return summary

    raise Arcor2Exception("Invalid package.")


async def get_opt_summary(path: str) -> None | PackageSummary:

    if not os.path.isfile(os.path.join(path, MAIN_SCRIPT_NAME)):
        logger.warn(f"Package at {path} does not contain main script.")
        return None

    package_dir = os.path.basename(path)
    package_meta = read_package_meta(package_dir)

    try:
        async with aiofiles.open(os.path.join(path, "data", "project.json")) as project_file:
            project = common.Project.from_json(await project_file.read())
    except (ValidationError, IOError, ValueError) as e:
        logger.error(f"Failed to read/parse project file of {package_dir}: {e}")

        return PackageSummary(package_dir, package_meta)

    return PackageSummary(package_dir, package_meta, ProjectMeta.from_project(project))


async def list_packages_cb(req: rpc.ListPackages.Request, ui: WsClient) -> rpc.ListPackages.Response:

    resp = rpc.ListPackages.Response()
    subfolders = [f.path for f in os.scandir(PROJECT_PATH) if f.is_dir()]
    resp.data = [
        ps
        for ps in await asyncio.gather(*[get_opt_summary(folder_path) for folder_path in subfolders])
        if ps is not None
    ]
    return resp


async def delete_package_cb(req: rpc.DeletePackage.Request, ui: WsClient) -> None:

    if RUNNING_PACKAGE_ID and RUNNING_PACKAGE_ID == req.args.id:
        raise Arcor2Exception("Package is being executed.")

    target_path = os.path.join(PROJECT_PATH, req.args.id)
    package_summary = await get_summary(target_path)

    try:
        await run_in_executor(shutil.rmtree, target_path, propagate=[FileNotFoundError])
    except FileNotFoundError:
        raise Arcor2Exception("Not found.")

    evt = events.PackageChanged(package_summary)
    evt.change_type = Event.Type.REMOVE
    asyncio.ensure_future(send_to_clients(evt))
    logger.info(f"Package '{package_summary.package_meta.name}' was removed.")
    return None


async def rename_package_cb(req: rpc.RenamePackage.Request, ui: WsClient) -> None:

    target_path = os.path.join(PROJECT_PATH, req.args.package_id, "package.json")

    pm = read_package_meta(req.args.package_id)
    old_name = pm.name
    pm.name = req.args.new_name

    async with aiofiles.open(target_path, mode="w") as pkg_file:
        await pkg_file.write(pm.to_json())

    evt = events.PackageChanged(await get_summary(os.path.join(PROJECT_PATH, req.args.package_id)))
    evt.change_type = Event.Type.UPDATE

    logger.info(f"Package '{old_name}' renamed to '{pm.name}'.")
    asyncio.ensure_future(send_to_clients(evt))


async def _version_cb(req: arcor2_rpc.common.Version.Request, ui: WsClient) -> arcor2_rpc.common.Version.Response:
    resp = arcor2_rpc.common.Version.Response()
    resp.data = resp.Data(await run_in_executor(arcor2_execution_data.version))
    return resp


async def send_to_clients(event: events.Event) -> None:

    if isinstance(event, ProjectException):
        logger.error(f"Script raised {event.data.type}. {event.data.message}")

    if CLIENTS:
        data = event.to_json()
        await asyncio.wait([client.send(data) for client in CLIENTS])


async def register(websocket: WsClient) -> None:

    logger.info("Registering new client")
    CLIENTS.add(websocket)

    tasks: list[Awaitable] = [websocket.send(PACKAGE_STATE_EVENT.to_json())]

    if PACKAGE_INFO_EVENT:
        tasks.append(websocket.send(PACKAGE_INFO_EVENT.to_json()))

    await asyncio.gather(*tasks)


async def unregister(websocket: WsClient) -> None:
    logger.info("Unregistering client")
    CLIENTS.remove(websocket)


RPC_DICT: ws_server.RPC_DICT_TYPE = {
    rpc.RunPackage.__name__: (rpc.RunPackage, run_package_cb),
    rpc.StopPackage.__name__: (rpc.StopPackage, stop_package_cb),
    rpc.PausePackage.__name__: (rpc.PausePackage, pause_package_cb),
    rpc.ResumePackage.__name__: (rpc.ResumePackage, resume_package_cb),
    rpc.StepAction.__name__: (rpc.StepAction, step_action_cb),
    rpc.UploadPackage.__name__: (rpc.UploadPackage, _upload_package_cb),
    rpc.ListPackages.__name__: (rpc.ListPackages, list_packages_cb),
    rpc.DeletePackage.__name__: (rpc.DeletePackage, delete_package_cb),
    rpc.RenamePackage.__name__: (rpc.RenamePackage, rename_package_cb),
    arcor2_rpc.common.Version.__name__: (arcor2_rpc.common.Version, _version_cb),
}


async def aio_main() -> None:

    if __debug__:
        logger.warn("Development mode. The service will shutdown on any unhandled exception.")

    logger.info(
        f"Execution service {arcor2_execution.version()} " f"(API version {arcor2_execution_data.version()}) started."
    )

    await websockets.server.serve(
        functools.partial(ws_server.server, logger=logger, register=register, unregister=unregister, rpc_dict=RPC_DICT),
        "0.0.0.0",
        port_from_url(URL),
    )


def main() -> None:

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "-d",
        "--debug",
        help="Set logging level to debug.",
        action="store_const",
        const=LogLevel.DEBUG,
        default=LogLevel.DEBUG if env.get_bool("ARCOR2_EXECUTION_DEBUG") else LogLevel.INFO,
    )
    parser.add_argument(
        "--version", action="version", version=arcor2_execution.version(), help="Shows version and exits."
    )
    parser.add_argument(
        "--api_version", action="version", version=arcor2_execution_data.version(), help="Shows API version and exits."
    )
    parser.add_argument(
        "-a",
        "--asyncio_debug",
        help="Turn on asyncio debug mode.",
        action="store_const",
        const=True,
        default=env.get_bool("ARCOR2_EXECUTION_ASYNCIO_DEBUG"),
    )

    args = parser.parse_args()
    logger.level = args.debug

    loop = asyncio.get_event_loop()
    loop.set_debug(enabled=args.asyncio_debug)

    loop.set_exception_handler(ws_server.custom_exception_handler)

    compile_json_schemas()

    run(aio_main(), loop=loop)


if __name__ == "__main__":
    main()
