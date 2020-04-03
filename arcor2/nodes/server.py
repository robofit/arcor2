#!/usr/bin/env python3
# -*- coding: utf-8 -*-


import argparse
import asyncio
import functools
import json
import sys
import uuid
from typing import Union, cast

import websockets
from aiologger.levels import LogLevel  # type: ignore

import arcor2
import arcor2.helpers as hlp
from arcor2 import action as action_mod
from arcor2 import aio_persistent_storage as storage
from arcor2 import nodes
from arcor2.data import events
from arcor2.data import rpc
from arcor2.data.helpers import RPC_MAPPING
from arcor2.parameter_plugins import PARAM_PLUGINS

import arcor2.server.globals as glob
import arcor2.server.objects_services_actions as osa
from arcor2.server import execution as exe, notifications as notif, rpc as srpc
from arcor2.server.project import open_project

# disables before/after messages, etc.
action_mod.HANDLE_ACTIONS = False


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
                exe.MANAGER_RPC_RESPONSES[resp.id].put_nowait(resp)

    except websockets.exceptions.ConnectionClosed:
        await glob.logger.error("Connection to manager closed.")


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
    await asyncio.wait([websockets.serve(bound_handler, '0.0.0.0', glob.PORT)])


async def _check_manager() -> None:
    """
    Loads project if it is loaded on manager (e.g. in a case when execution unit runs script and server is started).
    :return:
    """

    # TODO avoid cast
    resp = cast(rpc.execution.ProjectStateResponse,
                await exe.manager_request(rpc.execution.ProjectStateRequest(id=uuid.uuid4().int)))  # type: ignore

    if resp.data.id is not None and (glob.PROJECT is None or glob.PROJECT.id != resp.data.id):
        await open_project(resp.data.id)


async def list_meshes_cb(req: rpc.storage.ListMeshesRequest) -> Union[rpc.storage.ListMeshesResponse,
                                                                      hlp.RPC_RETURN_TYPES]:
    return rpc.storage.ListMeshesResponse(data=await storage.get_meshes())


async def register(websocket) -> None:

    await glob.logger.info("Registering new ui")
    glob.INTERFACES.add(websocket)

    await notif.event(websocket, events.SceneChanged(events.EventType.UPDATE, data=glob.SCENE))
    await notif.event(websocket, events.ProjectChanged(events.EventType.UPDATE, data=glob.PROJECT))

    # TODO avoid cast
    resp = cast(rpc.execution.ProjectStateResponse,
                await exe.manager_request(rpc.execution.ProjectStateRequest(id=uuid.uuid4().int)))  # type: ignore

    await asyncio.wait([websocket.send(events.ProjectStateEvent(data=resp.data.project).to_json())])
    if resp.data.action:
        await asyncio.wait([websocket.send(events.ActionStateEvent(data=resp.data.action).to_json())])
    if resp.data.action_args:
        await asyncio.wait([websocket.send(events.CurrentActionEvent(data=resp.data.action_args).to_json())])


async def unregister(websocket) -> None:
    await glob.logger.info("Unregistering ui")  # TODO print out some identifier
    glob.INTERFACES.remove(websocket)


async def system_info_cb(req: rpc.common.SystemInfoRequest) -> Union[rpc.common.SystemInfoResponse,
                                                                     hlp.RPC_RETURN_TYPES]:

    resp = rpc.common.SystemInfoResponse()
    resp.data.version = arcor2.version()
    resp.data.api_version = arcor2.api_version()
    resp.data.supported_parameter_types = set(PARAM_PLUGINS.keys())
    resp.data.supported_rpc_requests = {key.request for key in RPC_DICT.keys()}
    return resp


# TODO go through the modules and make the following automatically?
RPC_DICT: hlp.RPC_DICT_TYPE = {
    rpc.common.SystemInfoRequest: system_info_cb,
    rpc.execution.BuildProjectRequest: srpc.execution.build_project_cb,
    rpc.objects.GetObjectTypesRequest: srpc.objects.get_object_types_cb,
    rpc.objects.GetActionsRequest: srpc.objects.get_object_actions_cb,
    rpc.objects.NewObjectTypeRequest: srpc.objects.new_object_type_cb,
    rpc.robot.GetRobotMetaRequest: srpc.robot.get_robot_meta_cb,

    # TODO move to .scene
    rpc.objects.FocusObjectRequest: srpc.objects.focus_object_cb,
    rpc.objects.FocusObjectStartRequest: srpc.objects.focus_object_start_cb,
    rpc.objects.FocusObjectDoneRequest: srpc.objects.focus_object_done_cb,

    rpc.scene.NewSceneRequest: srpc.scene.new_scene_cb,
    rpc.scene.SaveSceneRequest: srpc.scene.save_scene_cb,
    rpc.scene.ListScenesRequest: srpc.scene.list_scenes_cb,
    rpc.scene.AddObjectToSceneRequest: srpc.scene.add_object_to_scene_cb,
    rpc.scene.AutoAddObjectToSceneRequest: srpc.scene.auto_add_object_to_scene_cb,
    rpc.scene.AddServiceToSceneRequest: srpc.scene.add_service_to_scene_cb,
    rpc.scene.RemoveFromSceneRequest: srpc.scene.remove_from_scene_cb,
    rpc.scene.SceneObjectUsageRequest: srpc.scene.scene_object_usage_request_cb,
    rpc.scene.OpenSceneRequest: srpc.scene.open_scene_cb,
    rpc.scene.CloseSceneRequest: srpc.scene.close_scene_cb,
    rpc.scene.UpdateObjectPoseRequest: srpc.scene.update_object_pose_cb,
    rpc.scene.RenameObjectRequest: srpc.scene.rename_object_cb,
    rpc.scene.RenameSceneRequest: srpc.scene.rename_scene_cb,
    rpc.scene.DeleteSceneRequest: srpc.scene.delete_scene_cb,
    rpc.scene.ProjectsWithSceneRequest: srpc.scene.projects_with_scene_cb,
    # TODO move to scene
    rpc.objects.UpdateObjectPoseUsingRobotRequest: srpc.scene.update_object_pose_using_robot_cb,
    rpc.objects.ActionParamValuesRequest: srpc.scene.action_param_values_cb,

    rpc.project.NewProjectRequest: srpc.project.new_project_cb,
    rpc.project.SaveProjectRequest: srpc.project.save_project_cb,
    rpc.project.OpenProjectRequest: srpc.project.open_project_cb,
    rpc.project.CloseProjectRequest: srpc.project.close_project_cb,
    rpc.project.ListProjectsRequest: srpc.project.list_projects_cb,
    rpc.project.ExecuteActionRequest: srpc.project.execute_action_cb,
    rpc.project.AddActionPointRequest: srpc.project.add_action_point_cb,
    rpc.project.UpdateActionPointRequest: srpc.project.update_action_point_cb,
    rpc.project.UpdateActionPointUsingRobotRequest: srpc.project.update_action_point_using_robot_cb,
    rpc.project.AddActionPointJointsRequest: srpc.project.add_action_point_joints_cb,
    rpc.project.UpdateActionPointJointsRequest: srpc.project.update_action_point_joints_cb,
    rpc.project.RemoveActionPointJointsRequest: srpc.project.remove_action_point_joints_cb,
    rpc.project.AddActionPointOrientationRequest: srpc.project.add_action_point_orientation_cb,
    rpc.project.UpdateActionPointOrientationRequest: srpc.project.update_action_point_orientation_cb,
    rpc.project.AddActionPointOrientationUsingRobotRequest: srpc.project.add_action_point_orientation_using_robot_cb,
    rpc.project.UpdateActionPointOrientationUsingRobotRequest:
        srpc.project.update_action_point_orientation_using_robot_cb,
    rpc.project.RemoveActionPointOrientationRequest: srpc.project.remove_action_point_orientation_cb,
    rpc.project.AddActionRequest: srpc.project.add_action_cb,
    rpc.project.UpdateActionRequest: srpc.project.update_action_cb,
    rpc.project.RemoveActionRequest: srpc.project.remove_action_cb,
    rpc.project.UpdateActionLogicRequest: srpc.project.update_action_logic_cb,

    rpc.services.GetServicesRequest: srpc.services.get_services_cb,
    rpc.storage.ListMeshesRequest: list_meshes_cb

}

# add Project Manager RPC API
for k, v in nodes.execution.RPC_DICT.items():

    if v.__name__.startswith("_"):
        continue

    RPC_DICT[k] = exe.manager_request


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

    loop.run_until_complete(asyncio.gather(exe.project_manager_client(handle_manager_incoming_messages),
                                           _initialize_server()))


if __name__ == "__main__":
    main()
