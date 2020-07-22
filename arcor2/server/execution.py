import asyncio
import base64
import os
import tempfile
import uuid
from typing import Dict, Optional, TYPE_CHECKING

import websockets
from websockets.server import WebSocketServerProtocol as WsClient

from arcor2 import helpers as hlp, rest
from arcor2.data import common, events, rpc
from arcor2.exceptions import Arcor2Exception
from arcor2.server import events as server_events, globals as glob, notifications as notif, project

if TYPE_CHECKING:
    ReqQueue = asyncio.Queue[rpc.common.Request]
    RespQueue = asyncio.Queue[rpc.common.Response]
else:
    ReqQueue = asyncio.Queue
    RespQueue = asyncio.Queue

MANAGER_RPC_REQUEST_QUEUE: ReqQueue = ReqQueue()
MANAGER_RPC_RESPONSES: Dict[int, RespQueue] = {}


async def run_temp_package(package_id: str) -> None:

    assert glob.PROJECT
    project_id = glob.PROJECT.id
    glob.TEMPORARY_PACKAGE = True

    await project.close_project(do_cleanup=False)

    exe_req = rpc.execution.RunPackageRequest(uuid.uuid4().int,
                                              args=rpc.execution.RunPackageArgs(package_id, cleanup_after_run=False))
    exe_resp = await manager_request(exe_req)

    if not exe_resp.result:
        await glob.logger.warning(f"Execution of temporary package failed with: {exe_resp.messages}.")
    else:
        await server_events.package_started.wait()
        await server_events.package_stopped.wait()
        await glob.logger.info("Temporary package stopped, let's remove it and reopen project.")

    glob.TEMPORARY_PACKAGE = False

    await manager_request(rpc.execution.DeletePackageRequest(uuid.uuid4().int, args=rpc.common.IdArgs(package_id)))

    await project.open_project(project_id)

    assert glob.SCENE
    assert glob.PROJECT

    asyncio.ensure_future(notif.broadcast_event(events.OpenProject(data=events.OpenProjectData(glob.SCENE.scene,
                                                                                               glob.PROJECT.project))))


async def build_and_upload_package(project_id: str, package_name: str) -> str:
    """
    Builds package and uploads it to the Execution unit.
    :param project_id:
    :param package_name:
    :return: generated package ID.
    """

    package_id = common.uid()

    # call build service
    # TODO store data in memory
    with tempfile.TemporaryDirectory() as tmpdirname:
        path = os.path.join(tmpdirname, "publish.zip")

        await hlp.run_in_executor(rest.download, f"{glob.BUILDER_URL}/project/{project_id}/publish", path,
                                  None, {"package_name": package_name})

        with open(path, "rb") as zip_file:
            b64_bytes = base64.b64encode(zip_file.read())
            b64_str = b64_bytes.decode()

    # send data to execution service
    exe_req = rpc.execution.UploadPackageRequest(uuid.uuid4().int,
                                                 args=rpc.execution.UploadPackageArgs(package_id, b64_str))
    exe_resp = await manager_request(exe_req)

    if not exe_resp.result:
        if not exe_resp.messages:
            raise Arcor2Exception("Upload to the Execution unit failed.")
        raise Arcor2Exception("\n".join(exe_resp.messages))

    return package_id


async def manager_request(req: rpc.common.Request, ui: Optional[WsClient] = None) -> rpc.common.Response:

    assert req.id not in MANAGER_RPC_RESPONSES

    MANAGER_RPC_RESPONSES[req.id] = RespQueue(maxsize=1)
    await MANAGER_RPC_REQUEST_QUEUE.put(req)

    resp = await MANAGER_RPC_RESPONSES[req.id].get()
    del MANAGER_RPC_RESPONSES[req.id]
    return resp


async def project_manager_client(handle_manager_incoming_messages) -> None:

    while True:

        await glob.logger.info("Attempting connection to manager...")

        try:

            async with websockets.connect(glob.MANAGER_URL) as manager_client:

                await glob.logger.info("Connected to manager.")

                future = asyncio.ensure_future(handle_manager_incoming_messages(manager_client))

                while True:

                    if future.done():
                        break

                    try:
                        msg = await asyncio.wait_for(MANAGER_RPC_REQUEST_QUEUE.get(), 1.0)
                    except asyncio.TimeoutError:
                        continue

                    try:
                        await manager_client.send(msg.to_json())
                    except websockets.exceptions.ConnectionClosed:
                        await MANAGER_RPC_REQUEST_QUEUE.put(msg)
                        break
        except ConnectionRefusedError as e:
            await glob.logger.error(e)
            await asyncio.sleep(delay=1.0)
