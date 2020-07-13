import asyncio
import importlib
import json
import keyword
import logging
import os
import re
import sys
import time
import traceback
from collections import deque
from datetime import datetime, timezone
from types import ModuleType
from typing import Any, Awaitable, Callable, Coroutine, Dict, Optional, Set, Tuple, Type, TypeVar

from aiologger.formatters.base import Formatter  # type: ignore
from aiologger.levels import LogLevel  # type: ignore

from dataclasses_jsonschema import ValidationError

import semver  # type: ignore

import websockets

from arcor2.data.events import Event, ProjectExceptionEvent, ProjectExceptionEventData
from arcor2.data.execution import PackageMeta
from arcor2.data.helpers import EVENT_MAPPING, RPC_MAPPING
from arcor2.data.rpc.common import Request, Response
from arcor2.exceptions import Arcor2Exception
from arcor2.settings import PROJECT_PATH


ReqT = TypeVar("ReqT", bound=Request)
RespT = TypeVar("RespT", bound=Response)

RPC_CB = Callable[[ReqT, websockets.WebSocketServerProtocol], Coroutine[Any, Any, Optional[RespT]]]
RPC_DICT_TYPE = Dict[Type[ReqT], RPC_CB]

EventT = TypeVar("EventT", bound=Event)
EVENT_DICT_TYPE = Dict[Type[EventT], Callable[[EventT, websockets.WebSocketServerProtocol], Coroutine[Any, Any, None]]]

LOG_FORMAT = '%(name)s - %(levelname)-8s: %(message)s'


class ImportClsException(Arcor2Exception):
    pass


class TypeDefException(Arcor2Exception):
    pass


def aiologger_formatter() -> Formatter:

    return Formatter(LOG_FORMAT)


def logger_formatter() -> logging.Formatter:

    return logging.Formatter(LOG_FORMAT)


def import_cls(module_cls: str) -> Tuple[ModuleType, Type[Any]]:
    """
    Gets module and class based on string like 'module/Cls'.
    :param module_cls:
    :return:
    """

    try:
        module_name, cls_name = module_cls.split('/')
    except (IndexError, ValueError):
        raise ImportClsException("Invalid format.")

    try:
        module = importlib.import_module(module_name)
    except ModuleNotFoundError:
        raise ImportClsException(f"Module '{module_name}' not found.")

    try:
        cls = getattr(module, cls_name)
    except AttributeError:
        raise ImportClsException(f"Class {cls_name} not found in module '{module_name}'.")

    return module, cls


def is_valid_identifier(value: str) -> bool:
    """
    Identifier (e.g. object id) will be used as variable name in the script - it should be in snake_case,
    not containing any special characters etc.
    :param value:
    :return:
    """

    return value.isidentifier() and not keyword.iskeyword(value) and value == camel_case_to_snake_case(value)


def is_valid_type(value: str) -> bool:
    """
    Value will be used as object type name - it should be in CamelCase,
    not containing any special characters etc.
    :param value:
    :return:
    """

    return value.isidentifier() and not keyword.iskeyword(value) and value == snake_case_to_camel_case(value)


_first_cap_re = re.compile('(.)([A-Z][a-z]+)')
_all_cap_re = re.compile('([a-z0-9])([A-Z])')


def camel_case_to_snake_case(camel_str: str) -> str:

    s1 = _first_cap_re.sub(r'\1_\2', camel_str)
    return _all_cap_re.sub(r'\1_\2', s1).lower()


def snake_case_to_camel_case(snake_str: str) -> str:

    return re.sub(r"(?:^|_)(.)", lambda m: m.group(1).upper(), snake_str)


async def send_json_to_client(client: websockets.WebSocketServerProtocol, data: str) -> None:

    try:
        await client.send(data)
    except websockets.exceptions.ConnectionClosed:
        pass


async def server(client: Any,
                 path: str,
                 logger: Any,
                 register: Callable[[Any], Awaitable[None]],
                 unregister: Callable[[Any], Awaitable[None]],
                 rpc_dict: RPC_DICT_TYPE,
                 event_dict: Optional[EVENT_DICT_TYPE] = None,
                 verbose: bool = False) -> None:

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
                await logger.error(f"Invalid data: '{message}'.")
                await logger.debug(e)
                continue

            if not isinstance(data, dict):
                await logger.error(f"Invalid data: '{data}'.")
                continue

            if "request" in data:  # ...then it is RPC

                try:
                    req_cls, resp_cls = RPC_MAPPING[data['request']]
                except KeyError:
                    await logger.error(f"Unknown RPC request: {data}.")
                    continue

                if req_cls not in rpc_dict:
                    await logger.debug(f"Ignoring RPC request: {data}.")
                    continue

                try:
                    req = req_cls.from_dict(data)
                except ValidationError as e:
                    await logger.error(f"Invalid RPC: {data}, error: {e}")
                    continue

                try:
                    resp = await rpc_dict[req_cls](req, client)
                except Arcor2Exception as e:
                    await logger.debug(e, exc_info=True)
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
                            await logger.debug(f"Request of type {req.request} will be silenced.")
                    elif req_per_sec < 1:
                        if req.request in ignored_reqs:
                            ignored_reqs.remove(req.request)

                    if req.request not in ignored_reqs:
                        asyncio.ensure_future(logger.debug(f"RPC request: {req}, result: {resp}"))

            elif "event" in data:  # ...event from UI

                try:
                    event_cls = EVENT_MAPPING[data["event"]]
                except KeyError as e:
                    await logger.error(f"Unknown event type: {e}.")
                    continue

                if event_cls not in event_dict:
                    await logger.debug(f"Ignoring event: {data}.")
                    continue

                try:
                    event = event_cls.from_dict(data)
                except ValidationError as e:
                    await logger.error(f"Invalid event: {data}, error: {e}")
                    continue

                await event_dict[event_cls](event, client)

            else:
                await logger.error(f"unsupported format of message: {data}")
    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        await unregister(client)


def format_stacktrace() -> str:
    parts = ["Traceback (most recent call last):\n"]
    parts.extend(traceback.format_stack(limit=25)[:-2])
    parts.extend(traceback.format_exception(*sys.exc_info())[1:])
    return "".join(parts)


def print_exception(e: Exception) -> None:

    if isinstance(e, Arcor2Exception):
        pee = ProjectExceptionEvent(data=ProjectExceptionEventData(e.message, e.__class__.__name__, True))
    else:
        pee = ProjectExceptionEvent(data=ProjectExceptionEventData(str(e), e.__class__.__name__))

    print(pee.to_json())
    sys.stdout.flush()

    with open("traceback-{}.txt".format(time.strftime("%Y%m%d-%H%M%S")), "w") as tb_file:
        tb_file.write(format_stacktrace())


S = TypeVar('S')


async def run_in_executor(func: Callable[..., S], *args) -> S:
    return await asyncio.get_event_loop().run_in_executor(None, func, *args)


T = TypeVar('T')


def type_def_from_source(source: str, type_name: str, output_type: Type[T]) -> Type[T]:

    mod = ModuleType('temp_module')
    try:
        exec(source, mod.__dict__)
    except Exception as e:  # exec might raise almost anything
        raise TypeDefException(e)

    try:
        cls_def = getattr(mod, type_name)
    except AttributeError:
        raise TypeDefException(f"Source does not contain class named '{type_name}'.")

    if not issubclass(cls_def, output_type):
        raise TypeDefException("Class is not of expected type.")

    return cls_def


def get_package_meta_path(package_id: str) -> str:

    return os.path.join(PROJECT_PATH, package_id, "package.json")


def read_package_meta(package_id: str) -> PackageMeta:

    try:
        with open(get_package_meta_path(package_id)) as pkg_file:
            return PackageMeta.from_json(pkg_file.read())
    except (IOError, ValidationError):
        return PackageMeta("N/A", datetime.fromtimestamp(0, tz=timezone.utc))


def write_package_meta(package_id: str, meta: PackageMeta) -> None:

    with open(get_package_meta_path(package_id), "w") as pkg_file:
        pkg_file.write(meta.to_json())


def check_compatibility(my_version: str, their_version: str) -> None:

    try:
        mv = semver.VersionInfo.parse(my_version)
        tv = semver.VersionInfo.parse(their_version)
    except ValueError as e:
        raise Arcor2Exception from e

    if mv.major != tv.major:
        raise Arcor2Exception("Different major varsion.")

    if mv.major == 0:
        if mv.minor != tv.minor:
            raise Arcor2Exception(f"Our version {my_version} is not compatible with {their_version}.")
    else:
        if mv.minor > tv.minor:
            raise Arcor2Exception(f"Our version {my_version} is outdated for {their_version}.")
