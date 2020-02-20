import traceback
import time
import sys
from typing import Optional, Dict, Callable, Tuple, Type, Union, Any, Awaitable, TypeVar
from types import ModuleType
import json
import asyncio
import importlib
import re
import keyword

from dataclasses_jsonschema import ValidationError

import websockets
from aiologger.formatters.base import Formatter  # type: ignore

from arcor2.data.rpc.common import Request
from arcor2.data.events import Event, ProjectExceptionEvent, ProjectExceptionEventData
from arcor2.data.helpers import RPC_MAPPING, EVENT_MAPPING
from arcor2.exceptions import Arcor2Exception
from arcor2.data.common import Pose, Position, Orientation


RPC_RETURN_TYPES = Union[None, Tuple[bool, str]]

# TODO what's wrong with following type?
# RPC_DICT_TYPE = Dict[Type[Request], Callable[[Request], Coroutine[Any, Any, Union[Response, RPC_RETURN_TYPES]]]]
RPC_DICT_TYPE = Dict[Type[Request], Any]

# TODO replace Any with WebsocketSomething
# EVENT_DICT_TYPE = Dict[Type[Event], Callable[[Any, Event], Coroutine[Any, Any, None]]]
EVENT_DICT_TYPE = Dict[Type[Event], Any]


class ImportClsException(Arcor2Exception):
    pass


class TypeDefException(Arcor2Exception):
    pass


def aiologger_formatter() -> Formatter:

    return Formatter('%(name)s - %(levelname)-8s: %(message)s')


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


async def server(client: Any,
                 path: str,
                 logger: Any,
                 register: Callable[[Any], Awaitable[None]],
                 unregister: Callable[[Any], Awaitable[None]],
                 rpc_dict: RPC_DICT_TYPE,
                 event_dict: Optional[EVENT_DICT_TYPE] = None) -> None:

    if event_dict is None:
        event_dict = {}

    await register(client)
    try:
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
                    resp = await rpc_dict[req_cls](req)
                except Arcor2Exception as e:
                    await logger.exception(e)
                    resp = False, "System error."

                if resp is None:  # default response
                    resp = resp_cls()
                elif isinstance(resp, tuple):
                    resp = resp_cls(result=resp[0], messages=[resp[1]])
                else:
                    assert isinstance(resp, resp_cls)

                resp.id = req.id

                await asyncio.wait([client.send(resp.to_json())])
                await logger.debug(f"RPC request: {req}, result: {resp}")

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

                await event_dict[event_cls](client, event)

            else:
                await logger.error(f"unsupported format of message: {data}")
    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        await unregister(client)


def format_stacktrace():
    parts = ["Traceback (most recent call last):\n"]
    parts.extend(traceback.format_stack(limit=25)[:-2])
    parts.extend(traceback.format_exception(*sys.exc_info())[1:])
    return "".join(parts)


def print_exception(e: Exception) -> None:

    pee = ProjectExceptionEvent(data=ProjectExceptionEventData(str(e),
                                                               e.__class__.__name__,
                                                               isinstance(e, Arcor2Exception)))
    print(pee.to_json())
    sys.stdout.flush()

    with open("traceback-{}.txt".format(time.strftime("%Y%m%d-%H%M%S")), "w") as tb_file:
        tb_file.write(format_stacktrace())


async def run_in_executor(func, *args):
    return await asyncio.get_event_loop().run_in_executor(None, func, *args)


def make_pose_rel(parent: Pose, child: Pose) -> Pose:
    """
    :param parent: e.g. scene object
    :param child:  e.g. action point
    :return: relative pose
    """

    p = Pose()

    p.position.x = child.position.x - parent.position.x
    p.position.y = child.position.y - parent.position.y
    p.position.z = child.position.z - parent.position.z

    p.orientation.set_from_quaternion(child.orientation.as_quaternion()/parent.orientation.as_quaternion())

    return p


def make_position_abs(parent: Position, child: Position) -> Position:

    p = Position()

    p.x = child.x + parent.x
    p.y = child.y + parent.y
    p.z = child.z + parent.z
    return p


def make_orientation_abs(parent: Orientation, child: Orientation) -> Orientation:

    p = Orientation()
    p.set_from_quaternion(child.as_quaternion() * parent.as_quaternion())
    return p


def make_pose_abs(parent: Pose, child: Pose) -> Pose:
    """
    :param parent: e.g. scene object
    :param child:  e.g. action point
    :return: absolute pose
    """

    p = Pose()
    p.position = make_position_abs(parent.position, child.position)
    p.orientation = make_orientation_abs(parent.orientation, child.orientation)
    return p


T = TypeVar('T')


def type_def_from_source(source: str, type_name: str, output_type: Type[T]) -> Type[T]:

    mod = ModuleType('temp_module')
    try:
        exec(source, mod.__dict__)
    except (ModuleNotFoundError, ImportError, SyntaxError) as e:
        raise TypeDefException(e)

    try:
        cls_def = getattr(mod, type_name)
    except AttributeError:
        raise TypeDefException(f"Source does not contain class named '{type_name}'.")

    if not issubclass(cls_def, output_type):
        raise TypeDefException(f"Class is not of expected type.")

    return cls_def
