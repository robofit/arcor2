import inspect
from typing import Dict, Tuple, Type

import arcor2.data.events
from arcor2.data import rpc
from arcor2.data.events import Event
from arcor2.data.rpc.common import Request, Response

RPC_MAPPING: Dict[str, Tuple[Type[Request], Type[Response]]] = {}

_requests: Dict[str, Type[Request]] = {}
_responses: Dict[str, Type[Response]] = {}

for rpc_module_name, rpc_module in inspect.getmembers(rpc, inspect.ismodule):
    for name, obj in inspect.getmembers(rpc_module, inspect.isclass):

        if not inspect.isclass(obj):
            continue

        if issubclass(obj, Request) and obj != Request:
            _requests[obj.request] = obj
        elif issubclass(obj, Response) and obj != Response:
            _responses[obj.response] = obj

assert _requests.keys() == _responses.keys(),\
    f"There is difference between requests/responses: " \
    f"{set(_requests.keys()).symmetric_difference(set(_responses.keys()))}"

for k, v in _requests.items():
    RPC_MAPPING[k] = (v, _responses[k])

EVENT_MAPPING: Dict[str, Type[Event]] = {}

for name, obj in inspect.getmembers(arcor2.data.events):

    if inspect.isclass(obj) and issubclass(obj, Event) and obj != Event:
        EVENT_MAPPING[obj.event] = obj
