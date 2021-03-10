import asyncio
import base64
import os
import tempfile
import uuid
from typing import TYPE_CHECKING, Dict, Optional

import websockets
from websockets.server import WebSocketServerProtocol as WsClient

from arcor2 import helpers as hlp
from arcor2 import rest
from arcor2.data import common, rpc
from arcor2.exceptions import Arcor2Exception
from arcor2_arserver import events as server_events
from arcor2_arserver import globals as glob
from arcor2_arserver import notifications as notif
from arcor2_arserver import project
from arcor2_arserver_data import events as sevts
from arcor2_build_data import URL as BUILD_URL
from arcor2_execution_data import URL as EXE_URL
from arcor2_execution_data import rpc as erpc

if TYPE_CHECKING:
    ReqQueue = asyncio.Queue[rpc.common.RPC.Request]
    RespQueue = asyncio.Queue[rpc.common.RPC.Response]
else:
    ReqQueue = asyncio.Queue
    RespQueue = asyncio.Queue

MANAGER_RPC_REQUEST_QUEUE: ReqQueue = ReqQueue()
MANAGER_RPC_RESPONSES: Dict[int, RespQueue] = {}


async def run_temp_package(package_id: str) -> None:

    assert glob.PROJECT
    project_id = glob.PROJECT.id
    glob.TEMPORARY_PACKAGE = True

    await project.close_project()
    req = erpc.RunPackage.Request
    exe_req = req(uuid.uuid4().int, args=req.Args(package_id, cleanup_after_run=False))
    exe_resp = await manager_request(exe_req)

    if not exe_resp.result:
        glob.logger.warning(f"Execution of temporary package failed with: {exe_resp.messages}.")
    else:
        await server_events.package_started.wait()
        await server_events.package_stopped.wait()
        glob.logger.info("Temporary package stopped, let's remove it and reopen project.")

    glob.TEMPORARY_PACKAGE = False

    await manager_request(erpc.DeletePackage.Request(uuid.uuid4().int, args=rpc.common.IdArgs(package_id)))

    await project.open_project(project_id)

    assert glob.SCENE
    assert glob.PROJECT

    asyncio.ensure_future(
        notif.broadcast_event(sevts.p.OpenProject(sevts.p.OpenProject.Data(glob.SCENE.scene, glob.PROJECT.project)))
    )


async def build_and_upload_package(project_id: str, package_name: str) -> str:
    """Builds package and uploads it to the Execution unit.

    :param project_id:
    :param package_name:
    :return: generated package ID.
    """

    package_id = common.uid("pkg")

    # call build service
    # TODO store data in memory
    with tempfile.TemporaryDirectory() as tmpdirname:
        path = os.path.join(tmpdirname, "publish.zip")

        await hlp.run_in_executor(
            rest.download,
            f"{BUILD_URL}/project/{project_id}/publish",
            path,
            {"packageName": package_name},
        )

        with open(path, "rb") as zip_file:
            b64_bytes = base64.b64encode(zip_file.read())
            b64_str = b64_bytes.decode()

    # send data to execution service
    exe_req = erpc.UploadPackage.Request(uuid.uuid4().int, args=erpc.UploadPackage.Request.Args(package_id, b64_str))
    exe_resp = await manager_request(exe_req)

    if not exe_resp.result:
        if not exe_resp.messages:
            raise Arcor2Exception("Upload to the Execution unit failed.")
        raise Arcor2Exception("\n".join(exe_resp.messages))

    return package_id


async def manager_request(req: rpc.common.RPC.Request, ui: Optional[WsClient] = None) -> rpc.common.RPC.Response:

    assert req.id not in MANAGER_RPC_RESPONSES

    MANAGER_RPC_RESPONSES[req.id] = RespQueue(maxsize=1)
    await MANAGER_RPC_REQUEST_QUEUE.put(req)
    resp = await MANAGER_RPC_RESPONSES[req.id].get()
    del MANAGER_RPC_RESPONSES[req.id]
    return resp


async def project_manager_client(handle_manager_incoming_messages) -> None:

    while True:

        glob.logger.info("Attempting connection to manager...")

        try:

            async with websockets.connect(EXE_URL) as manager_client:

                glob.logger.info("Connected to manager.")

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
            glob.logger.error(e)
            await asyncio.sleep(delay=1.0)
