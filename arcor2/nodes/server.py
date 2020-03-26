#!/usr/bin/env python3
# -*- coding: utf-8 -*-


import asyncio
import json
import functools
import sys
from typing import Callable, cast, Optional
import uuid
import argparse
import os

import websockets

import arcor2
from arcor2 import nodes
from arcor2.data import events
from arcor2.data.helpers import RPC_MAPPING
from arcor2 import aio_persistent_storage as storage
from arcor2.exceptions import Arcor2Exception
from arcor2.services import RobotService
from arcor2.parameter_plugins import TYPE_TO_PLUGIN, PARAM_PLUGINS
from arcor2 import action as action_mod
import arcor2.server.globals as glob
import arcor2.server.objects_services_actions as osa
from arcor2.server import srpc

# disables before/after messages, etc.
action_mod.HANDLE_ACTIONS = False

MANAGER_URL = os.getenv("ARCOR2_EXECUTION_URL", f"ws://0.0.0.0:{nodes.execution.PORT}")
BUILDER_URL = os.getenv("ARCOR2_BUILDER_URL", f"http://0.0.0.0:{nodes.build.PORT}")

PORT: int = int(os.getenv("ARCOR2_SERVER_PORT", 6789))


class RobotPoseException(Arcor2Exception):
    pass


async def handle_manager_incoming_messages(manager_client):

    try:

        async for message in manager_client:

            msg = json.loads(message)

            if "event" in msg and glob.INTERFACES:
                await asyncio.wait([intf.send(message) for intf in glob.INTERFACES])
            elif "response" in msg:

                # TODO handle potential errors
                _, resp_cls = RPC_MAPPING[msg["response"]]
                resp = resp_cls.from_dict(msg)
                glob.MANAGER_RPC_RESPONSES[resp.id].put_nowait(resp)

    except websockets.exceptions.ConnectionClosed:
        await glob.logger.error("Connection to manager closed.")


async def project_manager_client() -> None:

    while True:

        await glob.logger.info("Attempting connection to manager...")

        try:

            async with websockets.connect(MANAGER_URL) as manager_client:

                await glob.logger.info("Connected to manager.")

                future = asyncio.ensure_future(handle_manager_incoming_messages(manager_client))

                while True:

                    if future.done():
                        break

                    try:
                        msg = await asyncio.wait_for(glob.MANAGER_RPC_REQUEST_QUEUE.get(), 1.0)
                    except asyncio.TimeoutError:
                        continue

                    try:
                        await manager_client.send(msg.to_json())
                    except websockets.exceptions.ConnectionClosed:
                        await glob.MANAGER_RPC_REQUEST_QUEUE.put(msg)
                        break
        except ConnectionRefusedError as e:
            await glob.logger.error(e)
            await asyncio.sleep(delay=1.0)


def scene_event() -> events.SceneChangedEvent:

    return events.SceneChangedEvent(glob.SCENE)


def project_event() -> events.ProjectChangedEvent:

    return events.ProjectChangedEvent(glob.PROJECT)


async def notify(event: events.Event, exclude_ui=None):

    if (exclude_ui is None and glob.INTERFACES) or (exclude_ui and len(glob.INTERFACES) > 1):
        message = event.to_json()
        await asyncio.wait([intf.send(message) for intf in glob.INTERFACES if intf != exclude_ui])


async def _notify(interface, msg_source: Callable[[], events.Event]):

    await notify(msg_source(), interface)


async def notify_scene_change_to_others(interface: Optional[WebSocketServerProtocol] = None) -> None:

    await _notify(interface, scene_event)


async def notify_project_change_to_others(interface=None) -> None:

    await _notify(interface, project_event)


async def notify_scene(interface) -> None:
    message = scene_event().to_json()
    await asyncio.wait([interface.send(message)])


async def notify_project(interface) -> None:
    message = project_event().to_json()
    await asyncio.wait([interface.send(message)])


async def _initialize_server() -> None:

    while True:  # wait until Project service becomes available
        try:
            await storage.get_projects()
            break
        except storage.PersistentStorageException:
            await asyncio.sleep(1)

    # this has to be done sequentially as objects might depend on services so (all) services has to be known first
    await osa.get_service_types()
    await osa.get_object_types()

    await asyncio.wait([osa.get_object_actions(), _check_manager()])

    bound_handler = functools.partial(hlp.server, logger=glob.logger, register=register, unregister=unregister,
                                      rpc_dict=RPC_DICT, event_dict=EVENT_DICT)

    await glob.logger.info("Server initialized.")
    await asyncio.wait([websockets.serve(bound_handler, '0.0.0.0', PORT)])



async def _check_manager() -> None:
    """
    Loads project if it is loaded on manager
    :return:
    """

    # TODO avoid cast
    resp = cast(rpc.execution.ProjectStateResponse,
                await manager_request(rpc.execution.ProjectStateRequest(id=uuid.uuid4().int)))  # type: ignore

    # TODO is this still needed?
    # if resp.data.id is not None and (PROJECT is None or PROJECT.id != resp.data.id):
    #    await open_project(resp.data.id)


async def manager_request(req: rpc.common.Request) -> rpc.common.Response:

    assert req.id not in glob.MANAGER_RPC_RESPONSES

    glob.MANAGER_RPC_RESPONSES[req.id] = glob.RespQueue(maxsize=1)
    await glob.MANAGER_RPC_REQUEST_QUEUE.put(req)

    resp = await glob.MANAGER_RPC_RESPONSES[req.id].get()
    del glob.MANAGER_RPC_RESPONSES[req.id]
    return resp



async def list_meshes_cb(req: rpc.storage.ListMeshesRequest) -> Union[rpc.storage.ListMeshesResponse,
                                                                      hlp.RPC_RETURN_TYPES]:
    return rpc.storage.ListMeshesResponse(data=await storage.get_meshes())


async def register(websocket) -> None:

    await glob.logger.info("Registering new ui")
    glob.INTERFACES.add(websocket)

    await notify_scene(websocket)
    await notify_project(websocket)

    # TODO avoid cast
    resp = cast(rpc.execution.ProjectStateResponse,
                await manager_request(rpc.execution.ProjectStateRequest(id=uuid.uuid4().int)))  # type: ignore

    await asyncio.wait([websocket.send(events.ProjectStateEvent(data=resp.data.project).to_json())])
    if resp.data.action:
        await asyncio.wait([websocket.send(events.ActionStateEvent(data=resp.data.action).to_json())])
    if resp.data.action_args:
        await asyncio.wait([websocket.send(events.CurrentActionEvent(data=resp.data.action_args).to_json())])


async def unregister(websocket) -> None:
    await glob.logger.info("Unregistering ui")  # TODO print out some identifier
    glob.INTERFACES.remove(websocket)


async def collision(obj: Generic,
                    rs: Optional[RobotService] = None, *, add: bool = False, remove: bool = False) -> None:
    """

    :param obj: Instance of the object.
    :param add:
    :param remove:
    :param rs:
    :return:
    """

    assert add ^ remove

    if not obj.collision_model:
        return

    if rs is None:
        rs = osa.find_robot_service()
    if rs:
        try:
            # TODO notify user somehow when something went wrong?
            await hlp.run_in_executor(rs.add_collision if add else rs.remove_collision, obj)
        except Arcor2Exception as e:
            await glob.logger.error(e)


async def system_info_cb(req: rpc.common.SystemInfoRequest) -> Union[rpc.common.SystemInfoResponse,
                                                                     hlp.RPC_RETURN_TYPES]:

    resp = rpc.common.SystemInfoResponse()
    resp.data.version = arcor2.version()
    resp.data.api_version = arcor2.api_version()
    resp.data.supported_parameter_types = set(PARAM_PLUGINS.keys())
    return resp


RPC_DICT: hlp.RPC_DICT_TYPE = {
    rpc.common.SystemInfoRequest: system_info_cb,
    rpc.execution.BuildProjectRequest: srpc.execution.build_project_cb,
    rpc.objects.GetObjectTypesRequest: srpc.objects.get_object_types_cb,
    rpc.objects.GetActionsRequest: srpc.objects.get_object_actions_cb,
    rpc.objects.UpdateActionPointPoseRequest: srpc.objects.update_action_point_cb,
    rpc.objects.UpdateActionPointJointsRequest: srpc.objects.update_ap_joints_cb,
    rpc.objects.UpdateActionObjectPoseRequest: srpc.objects.update_action_object_cb,
    rpc.objects.NewObjectTypeRequest: srpc.objects.new_object_type_cb,
    rpc.objects.FocusObjectRequest: srpc.objects.focus_object_cb,
    rpc.objects.FocusObjectStartRequest: srpc.objects.focus_object_start_cb,
    rpc.objects.FocusObjectDoneRequest: srpc.objects.focus_object_done_cb,
    rpc.objects.ActionParamValuesRequest: srpc.objects.action_param_values_cb,
    rpc.robot.GetRobotMetaRequest: srpc.robot.get_robot_meta_cb,

    rpc.scene.NewSceneRequest: srpc.scene.new_scene_cb,
    rpc.scene.SaveSceneRequest: srpc.scene.save_scene_cb,
    rpc.scene.ListScenesRequest: srpc.scene.list_scenes_cb,
    rpc.scene.AddObjectToSceneRequest: srpc.scene.add_object_to_scene_cb,
    rpc.scene.AutoAddObjectToSceneRequest: srpc.scene.auto_add_object_to_scene_cb,
    rpc.scene.AddServiceToSceneRequest: srpc.scene.add_service_to_scene_cb,
    rpc.scene.RemoveFromSceneRequest: srpc.scene.remove_from_scene_cb,
    rpc.scene.SceneObjectUsageRequest: srpc.scene.scene_object_usage_request_cb,
    rpc.scene.OpenSceneRequest: srpc.scene.open_scene_cb,

    rpc.project.SaveProjectRequest: srpc.project.save_project_cb,
    rpc.project.OpenProjectRequest: srpc.project.open_project_cb,
    rpc.project.ListProjectsRequest: srpc.project.list_projects_cb,
    rpc.project.ExecuteActionRequest: srpc.project.execute_action_cb,
    rpc.services.GetServicesRequest: srpc.project.get_services_cb,
    rpc.storage.ListMeshesRequest: srpc.project.list_meshes_cb
}

# add Project Manager RPC API
for k, v in nodes.execution.RPC_DICT.items():

    if v.__name__.startswith("_"):
        continue

    RPC_DICT[k] = manager_request


# events from clients
EVENT_DICT: hlp.EVENT_DICT_TYPE = {}


def main():

    assert sys.version_info >= (3, 8)

    parser = argparse.ArgumentParser()

    parser.add_argument("-v", "--verbose", help="Increase output verbosity",
                        action="store_const", const=LogLevel.DEBUG, default=LogLevel.INFO)
    parser.add_argument('--version', action='version', version=arcor2.version(),
                        help="Shows ARCOR2 version and exits.")
    parser.add_argument('--api_version', action='version', version=arcor2.api_version(),
                        help="Shows API version and exits.")
    parser.add_argument("-a", "--asyncio_debug", help="Turn on asyncio debug mode.",
                        action="store_const", const=True, default=False)

    args = parser.parse_args()
    glob.logger.level = args.verbose

    loop = asyncio.get_event_loop()
    loop.set_debug(enabled=args.asyncio_debug)

    loop.run_until_complete(asyncio.wait([asyncio.gather(project_manager_client(), _initialize_server())]))


if __name__ == "__main__":
    main()
