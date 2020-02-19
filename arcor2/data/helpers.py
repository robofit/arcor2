import inspect
from typing import Dict, Tuple, Type
from arcor2.data.rpc.common import Request, Response
from arcor2.data.events import Event
import arcor2.data.events
from arcor2.data import rpc


RPC_MAPPING: Dict[str, Tuple[Type[Request], Type[Response]]] = {}

_requests: Dict[str, Type[Request]] = {}
_responses: Dict[str, Type[Response]] = {}

# TODO avoid explicit naming of all sub-modules in rpc module
for rpc_module in (rpc.common, rpc.execution, rpc.objects, rpc.robot, rpc.scene_project, rpc.services, rpc.storage):
    for name, obj in inspect.getmembers(rpc_module):

        if not inspect.isclass(obj):
            continue

        if issubclass(obj, Request) and obj != Request:
            _requests[obj.request] = obj
        elif issubclass(obj, Response) and obj != Response:
            _responses[obj.response] = obj

assert _requests.keys() == _responses.keys()

for k, v in _requests.items():
    RPC_MAPPING[k] = (v, _responses[k])

EVENT_MAPPING: Dict[str, Type[Event]] = {}

for name, obj in inspect.getmembers(arcor2.data.events):

    if inspect.isclass(obj) and issubclass(obj, Event) and obj != Event:
        EVENT_MAPPING[obj.event] = obj
