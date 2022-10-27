import asyncio
import time
from collections import deque
from typing import Any, Awaitable, Callable, Coroutine, TypeVar

import websockets
from aiologger.levels import LogLevel
from dataclasses_jsonschema import ValidationError
from websockets.server import WebSocketServerProtocol as WsClient

from arcor2 import env, json
from arcor2.data.events import Event
from arcor2.data.rpc.common import RPC
from arcor2.exceptions import Arcor2Exception

MAX_RPC_DURATION = env.get_float("ARCOR2_MAX_RPC_DURATION", 0.1)

RPCT = TypeVar("RPCT", bound=RPC)
ReqT = TypeVar("ReqT", bound=RPC.Request)
RespT = TypeVar("RespT", bound=RPC.Response)

RPC_CB = Callable[[ReqT, WsClient], Coroutine[Any, Any, None | RespT]]
RPC_DICT_TYPE = dict[str, tuple[type[RPC], RPC_CB]]

EventT = TypeVar("EventT", bound=Event)
EVENT_DICT_TYPE = dict[str, tuple[type[EventT], Callable[[EventT, WsClient], Coroutine[Any, Any, None]]]]


def custom_exception_handler(loop: asyncio.AbstractEventLoop, context: dict[str, Any]) -> None:

    # it is also possible to use aiorun.run with stop_on_unhandled_errors=True but this prints much more useful info
    loop.default_exception_handler(context)

    if __debug__:  # stop loop while debugging, try to continue in production
        loop.stop()


async def send_json_to_client(client: WsClient, data: str) -> None:

    try:
        await client.send(data)
    except websockets.exceptions.ConnectionClosed:
        pass


async def server(
    client: Any,
    logger: Any,
    register: Callable[[Any], Awaitable[None]],
    unregister: Callable[[Any], Awaitable[None]],
    rpc_dict: RPC_DICT_TYPE,
    event_dict: None | EVENT_DICT_TYPE = None,
    verbose: bool = False,
) -> None:
    async def handle_message(msg: str) -> None:

        try:
            data = json.loads(msg)
        except json.JsonException as e:
            logger.error(f"Invalid data: '{msg}'.")
            logger.debug(e)
            return

        if not isinstance(data, dict):
            logger.error(f"Invalid data: '{data}'.")
            return

        if "request" in data:  # ...then it is RPC

            req_type = data["request"]

            try:
                rpc_cls, rpc_cb = rpc_dict[req_type]
            except KeyError:
                logger.error(f"Unknown RPC request: {data}.")
                return

            assert req_type == rpc_cls.__name__

            try:
                req = rpc_cls.Request.from_dict(data)
            except ValidationError as e:
                logger.error(f"Invalid RPC: {data}, error: {e}")
                return
            except Arcor2Exception as e:
                # this might happen if e.g. some dataclass does additional validation of values in its __post_init__
                try:
                    await client.send(rpc_cls.Response(data["id"], False, messages=[str(e)]).to_json())
                    logger.debug(e, exc_info=True)
                except (KeyError, websockets.exceptions.ConnectionClosed):
                    pass
                return

            else:

                try:
                    rpc_start = time.monotonic()
                    resp = await rpc_cb(req, client)
                    rpc_dur = time.monotonic() - rpc_start
                    if rpc_dur > MAX_RPC_DURATION:
                        logger.warn(f"{req.request} callback took {rpc_dur:.3f}s.")

                except Arcor2Exception as e:
                    logger.debug(e, exc_info=True)
                    resp = rpc_cls.Response(req.id, False, [str(e)])
                else:
                    if resp is None:  # default response
                        resp = rpc_cls.Response(req.id, True)
                    else:
                        assert isinstance(resp, rpc_cls.Response)
                        resp.id = req.id

            try:
                await client.send(resp.to_json())
            except websockets.exceptions.ConnectionClosed:
                return

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
                    logger.debug(f"RPC request: {req}, result: {resp}")

        elif "event" in data:  # ...event from UI

            assert event_dict

            try:
                event_cls, event_cb = event_dict[data["event"]]
            except KeyError as e:
                logger.error(f"Unknown event type: {e}.")
                return

            try:
                event = event_cls.from_dict(data)
            except ValidationError as e:
                logger.error(f"Invalid event: {data}, error: {e}")
                return

            await event_cb(event, client)

        else:
            logger.error(f"unsupported format of message: {data}")

    if event_dict is None:
        event_dict = {}

    req_last_ts: dict[str, deque] = {}
    ignored_reqs: set[str] = set()

    try:

        await register(client)

        loop = asyncio.get_event_loop()

        async for message in client:
            loop.create_task(handle_message(message))

    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        await unregister(client)
