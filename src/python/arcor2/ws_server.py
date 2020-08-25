import asyncio
import json
import time
from collections import deque
from typing import Any, Awaitable, Callable, Coroutine, Dict, Optional, Set, Type, TypeVar

import websockets
from aiologger.levels import LogLevel  # type: ignore
from dataclasses_jsonschema import ValidationError

from arcor2.data.events import Event
from arcor2.data.helpers import EVENT_MAPPING, RPC_MAPPING
from arcor2.data.rpc.common import Request, Response
from arcor2.exceptions import Arcor2Exception

ReqT = TypeVar("ReqT", bound=Request)
RespT = TypeVar("RespT", bound=Response)

RPC_CB = Callable[[ReqT, websockets.WebSocketServerProtocol], Coroutine[Any, Any, Optional[RespT]]]
RPC_DICT_TYPE = Dict[Type[ReqT], RPC_CB]

EventT = TypeVar("EventT", bound=Event)
EVENT_DICT_TYPE = Dict[Type[EventT], Callable[[EventT, websockets.WebSocketServerProtocol], Coroutine[Any, Any, None]]]


async def send_json_to_client(client: websockets.WebSocketServerProtocol, data: str) -> None:

    try:
        await client.send(data)
    except websockets.exceptions.ConnectionClosed:
        pass


async def server(
    client: Any,
    path: str,
    logger: Any,
    register: Callable[[Any], Awaitable[None]],
    unregister: Callable[[Any], Awaitable[None]],
    rpc_dict: RPC_DICT_TYPE,
    event_dict: Optional[EVENT_DICT_TYPE] = None,
    verbose: bool = False,
) -> None:

    if event_dict is None:
        event_dict = {}

    req_last_ts: Dict[str, deque] = {}
    ignored_reqs: Set[str] = set()

    try:

        await register(client)

        async for message in client:

            try:
                data = json.loads(message)
            except json.decoder.JSONDecodeError as e:
                logger.error(f"Invalid data: '{message}'.")
                logger.debug(e)
                continue

            if not isinstance(data, dict):
                logger.error(f"Invalid data: '{data}'.")
                continue

            if "request" in data:  # ...then it is RPC

                try:
                    req_cls, resp_cls = RPC_MAPPING[data["request"]]
                except KeyError:
                    logger.error(f"Unknown RPC request: {data}.")
                    continue

                if req_cls not in rpc_dict:
                    logger.debug(f"Ignoring RPC request: {data}.")
                    continue

                try:
                    req = req_cls.from_dict(data)
                except ValidationError as e:
                    logger.error(f"Invalid RPC: {data}, error: {e}")
                    continue

                try:
                    resp = await rpc_dict[req_cls](req, client)
                except Arcor2Exception as e:
                    logger.debug(e, exc_info=True)
                    resp = resp_cls()
                    resp.result = False
                    resp.messages = [e.message]

                if resp is None:  # default response
                    resp = resp_cls()
                else:
                    assert isinstance(resp, resp_cls)

                resp.id = req.id

                await asyncio.wait([client.send(resp.to_json())])

                if logger.level == LogLevel.DEBUG:

                    # Silencing of repetitive log messages
                    # ...maybe this could be done better and in a more general way using logging.Filter?

                    now = time.monotonic()
                    if req.request not in req_last_ts:
                        req_last_ts[req.request] = deque()

                    while req_last_ts[req.request]:
                        if req_last_ts[req.request][0] < now - 5.0:
                            req_last_ts[req.request].popleft()
                        else:
                            break

                    req_last_ts[req.request].append(now)
                    req_per_sec = len(req_last_ts[req.request]) / 5.0

                    if req_per_sec > 2:
                        if req.request not in ignored_reqs:
                            ignored_reqs.add(req.request)
                            logger.debug(f"Request of type {req.request} will be silenced.")
                    elif req_per_sec < 1:
                        if req.request in ignored_reqs:
                            ignored_reqs.remove(req.request)

                    if req.request not in ignored_reqs:
                        asyncio.ensure_future(logger.debug(f"RPC request: {req}, result: {resp}"))

            elif "event" in data:  # ...event from UI

                try:
                    event_cls = EVENT_MAPPING[data["event"]]
                except KeyError as e:
                    logger.error(f"Unknown event type: {e}.")
                    continue

                if event_cls not in event_dict:
                    logger.debug(f"Ignoring event: {data}.")
                    continue

                try:
                    event = event_cls.from_dict(data)
                except ValidationError as e:
                    logger.error(f"Invalid event: {data}, error: {e}")
                    continue

                await event_dict[event_cls](event, client)

            else:
                logger.error(f"unsupported format of message: {data}")
    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        await unregister(client)
