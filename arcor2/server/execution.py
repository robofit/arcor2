import asyncio
from typing import TYPE_CHECKING, Dict, Optional

import websockets
from websockets.server import WebSocketServerProtocol as WsClient

from arcor2.data import rpc

from arcor2.server import globals as glob


if TYPE_CHECKING:
    ReqQueue = asyncio.Queue[rpc.common.Request]
    RespQueue = asyncio.Queue[rpc.common.Response]
else:
    ReqQueue = asyncio.Queue
    RespQueue = asyncio.Queue

MANAGER_RPC_REQUEST_QUEUE: ReqQueue = ReqQueue()
MANAGER_RPC_RESPONSES: Dict[int, RespQueue] = {}


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
