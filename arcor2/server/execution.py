import asyncio
from typing import TYPE_CHECKING, Dict

from arcor2.data import rpc


if TYPE_CHECKING:
    ReqQueue = asyncio.Queue[rpc.common.Request]
    RespQueue = asyncio.Queue[rpc.common.Response]
else:
    ReqQueue = asyncio.Queue
    RespQueue = asyncio.Queue

MANAGER_RPC_REQUEST_QUEUE: ReqQueue = ReqQueue()
MANAGER_RPC_RESPONSES: Dict[int, RespQueue] = {}


async def manager_request(req: rpc.common.Request) -> rpc.common.Response:

    assert req.id not in MANAGER_RPC_RESPONSES

    MANAGER_RPC_RESPONSES[req.id] = RespQueue(maxsize=1)
    await MANAGER_RPC_REQUEST_QUEUE.put(req)

    resp = await MANAGER_RPC_RESPONSES[req.id].get()
    del MANAGER_RPC_RESPONSES[req.id]
    return resp