from typing import Optional, List, Dict, Callable, Tuple, Type, Union, Any, Awaitable, Coroutine
from types import ModuleType
import json
import asyncio
import importlib
import re

import websockets
from aiologger.formatters.base import Formatter  # type: ignore

from arcor2.data.common import DataClassEncoder
from arcor2.exceptions import Arcor2Exception

_first_cap_re = re.compile('(.)([A-Z][a-z]+)')
_all_cap_re = re.compile('([a-z0-9])([A-Z])')


class ImportClsException(Arcor2Exception):
    pass


def aiologger_formatter():

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


def camel_case_to_snake_case(camel_str: str) -> str:

    s1 = _first_cap_re.sub(r'\1_\2', camel_str)
    return _all_cap_re.sub(r'\1_\2', s1).lower()


def snake_case_to_camel_case(snake_str: str) -> str:

    first, *others = snake_str.split('_')
    return ''.join([first.lower(), *map(str.title, others)])


# TODO define Response dataclass instead
def response(resp_to: str, result: bool = True, messages: Optional[List[str]] = None,
             data: Optional[Union[Dict, List]] = None) -> Dict:  # type: ignore

    if messages is None:
        messages = []

    if data is None:
        data = {}

    return {"response": resp_to, "result": result, "messages": messages, "data": data}


class RpcPlugin:

    def post_hook(self, req: str, args: Dict[str, Any], resp: Dict[str, Any]) -> None:
        pass


def rpc(logger: Any, plugins: Optional[List[RpcPlugin]] = None) -> Callable[..., Any]:
    def rpc_inner(f: Callable[..., Awaitable[Any]]) -> Callable[[str, Any, Dict[str, Any], Optional[int]],
                                                                Coroutine[Any, Any, None]]:
        async def wrapper(req: str, ui: Any, args: Dict[str, Any], req_id: Optional[int] = None) -> None:

            msg = await f(req, ui, args)

            if msg is None:
                await logger.debug(f"Ignoring invalid RPC request: {req}, args: {args}")
                return

            if req_id is not None:
                msg["req_id"] = req_id
            j = json.dumps(msg, cls=DataClassEncoder)

            await asyncio.wait([ui.send(j)])
            await logger.debug(f"RPC request: {req}, args: {args}, req_id: {req_id}, result: {j}")

            if plugins:
                for plugin in plugins:
                    await asyncio.get_event_loop().run_in_executor(None, plugin.post_hook, req, args, msg)

        return wrapper
    return rpc_inner


async def server(client: Any,
                 path: str,
                 logger: Any,
                 register: Callable[..., Awaitable[Any]],
                 unregister: Callable[..., Awaitable[Any]],
                 rpc_dict: Dict[str, Callable[..., Any]],
                 event_dict: Optional[Dict[str, Callable[..., Any]]] = None) -> None:

    if event_dict is None:
        event_dict = {}

    await register(client)
    try:
        async for message in client:

            try:
                data = json.loads(message)
            except json.decoder.JSONDecodeError as e:
                await logger.error(e)
                continue

            if "request" in data:  # ...then it is RPC
                try:
                    rpc_func = rpc_dict[data['request']]
                except KeyError:
                    await logger.error(f"Unknown RPC request: {data}.")
                    continue

                await rpc_func(data['request'], client, data.get("args", {}), data.get("req_id", None))

            elif "event" in data:  # ...event from UI

                try:
                    event_func = event_dict[data["event"]]
                except KeyError as e:
                    await logger.error(f"Unknown event type: {e}.")
                    continue

                await event_func(client, data["data"])

            else:
                await logger.error(f"unsupported format of message: {data}")
    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        await unregister(client)
