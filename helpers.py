import inspect
from typing import Optional, List, Dict, Callable
import json
import asyncio
import websockets
import re
import fastjsonschema
import os

import arcor2
import arcor2.object_types
from arcor2.object_types import Generic

_first_cap_re = re.compile('(.)([A-Z][a-z]+)')
_all_cap_re = re.compile('([a-z0-9])([A-Z])')


def convert_cc(name):
    s1 = _first_cap_re.sub(r'\1_\2', name)
    return _all_cap_re.sub(r'\1_\2', s1).lower()


def response(resp_to: str, result: bool = True, messages: Optional[List[str]] = None) -> Dict:

    if messages is None:
        messages = []

    return {"response": resp_to, "result": result, "messages": messages}


def rpc(logger):
    def rpc_inner(f: Callable) -> Callable:
        async def wrapper(req: str, ui, args: Dict, req_id: Optional[int] = None):

            msg = await f(req, ui, args)
            if req_id is not None:
                msg["req_id"] = req_id
            j = json.dumps(msg)
            await asyncio.wait([ui.send(j)])
            await logger.debug(f"RPC request: {req}, args: {args}: {req_id}, result: {j}")

        return wrapper
    return rpc_inner


def validate_event(logger, validate_func: Callable, arg_idx: int = 1):
    def validate_inner(f: Callable) -> Callable:
        async def wrapper(*args, **kwargs):
            try:
                # validate_func may add default values
                args[arg_idx].update(validate_func(args[arg_idx]))
            except fastjsonschema.JsonSchemaException as e:
                await logger.error(str(e))
                return
            return await f(*args, **kwargs)
        return wrapper
    return validate_inner


def read_schema(schema: str) -> Dict:

    with open(os.path.join(arcor2.__path__[0], "json-schemas", schema + ".json"), 'r') as f:
        return json.loads(f.read())


async def server(client, path, logger, register, unregister, rpc_dict: Dict, event_dict: Optional[Dict] = None) -> None:

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
                except KeyError as e:
                    await logger.error(f"Unknown RPC request: {e}.")
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


def built_in_types():
    """
    Yields class name and class definition tuple
    """

    for cls in inspect.getmembers(arcor2.object_types, inspect.isclass):
        if not issubclass(cls[1], Generic):
            continue

        yield cls[0], cls[1]


def built_in_types_names():

    names = set()

    for type_name, type_def in built_in_types():
        names.add(type_name)

    return names
