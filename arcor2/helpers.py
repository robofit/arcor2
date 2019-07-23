import inspect
from typing import Optional, List, Dict, Callable, Tuple, Type, Union, Set
from types import ModuleType
import json
import asyncio
import importlib
import re

import websockets  # type: ignore

import arcor2
import arcor2.object_types
from arcor2.object_types import Generic
from arcor2.data import DataClassEncoder, ActionIOEnum, ProjectObject, Project, Action
from arcor2.exceptions import Arcor2Exception


_first_cap_re = re.compile('(.)([A-Z][a-z]+)')
_all_cap_re = re.compile('([a-z0-9])([A-Z])')


class ImportClsException(Arcor2Exception):
    pass


def import_cls(module_cls: str) -> Tuple[ModuleType, Type]:
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


def convert_cc(name):
    s1 = _first_cap_re.sub(r'\1_\2', name)
    return _all_cap_re.sub(r'\1_\2', s1).lower()


# TODO define Response dataclass instead?
def response(resp_to: str, result: bool = True, messages: Optional[List[str]] = None,
             data: Optional[Union[Dict, List]] = None) -> Dict:

    if messages is None:
        messages = []

    if data is None:
        data = {}

    return {"response": resp_to, "result": result, "messages": messages, "data": data}


class RpcPlugin:

    def post_hook(self, req: str, args: Dict, resp: Dict):
        pass


def rpc(logger, plugins: Optional[List[RpcPlugin]] = None):
    def rpc_inner(f: Callable) -> Callable:
        async def wrapper(req: str, ui, args: Dict, req_id: Optional[int] = None):

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


def built_in_types_names() -> Set:

    names = set()

    for type_name, _ in built_in_types():
        names.add(type_name)

    return names


def get_actions_cache(project: Project) -> Tuple[Dict[str, Action], Union[str, None], Union[str, None]]:

    actions_cache = {}
    first_action_id = None
    last_action_id = None

    for obj in project.objects:
        for aps in obj.action_points:
            for act in aps.actions:
                actions_cache[act.id] = act
                if act.inputs and act.inputs[0].default == ActionIOEnum.FIRST:
                    first_action_id = act.id
                elif act.outputs and act.outputs[0].default == ActionIOEnum.LAST:
                    last_action_id = act.id

    return actions_cache, first_action_id, last_action_id


def get_objects_cache(project: Project, id_to_var: bool = False) -> Dict[str, ProjectObject]:

    cache: Dict[str, ProjectObject] = {}

    for obj in project.objects:
        if id_to_var:
            cache[convert_cc(obj.id)] = obj
        else:
            cache[obj.id] = obj

    return cache


def clear_project_logic(project: Project):

    for obj in project.objects:
        for act_point in obj.action_points:
            for action in act_point.actions:
                action.inputs.clear()
                action.outputs.clear()
