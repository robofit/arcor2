import asyncio
import time
from typing import Union, Awaitable, Dict

from websockets.server import WebSocketServerProtocol as WsClient

from arcor2.data import rpc, events
from arcor2 import helpers as hlp

from arcor2.server import globals as glob
from arcor2.server.robot import get_robot_joints, get_end_effector_pose, get_end_effectors, get_grippers, get_suctions
from arcor2.server.decorators import scene_needed


ROBOT_JOINTS_TASKS: Dict[str, Awaitable] = {}


async def robot_joints_event(robot_id: str):

    while glob.SCENE:

        start = time.monotonic()

        evt = events.RobotJointsEvent()
        evt.data = events.RobotJointsData(robot_id, (await get_robot_joints(robot_id)))
        evt_json = evt.to_json()

        tasks = []

        for ui in glob.ROBOT_JOINTS_REGISTERED_UIS[robot_id]:

            # TODO check if ui is still in glob.INTERFACES (or remove ui from ROBOT_JOINTS_REGISTERED_UIS when it is gone?)
            tasks.append(ui.send(evt_json))

        await asyncio.gather(*tasks)

        end = time.monotonic()
        await asyncio.sleep(0.1-(end-start))


async def get_robot_meta_cb(req: rpc.robot.GetRobotMetaRequest, ui: WsClient) -> Union[rpc.robot.GetRobotMetaResponse,
                                                                         hlp.RPC_RETURN_TYPES]:

    return rpc.robot.GetRobotMetaResponse(data=list(glob.ROBOT_META.values()))


@scene_needed
async def get_robot_joints_cb(req: rpc.robot.GetRobotJointsRequest, ui: WsClient) -> \
        Union[rpc.robot.GetRobotJointsResponse, hlp.RPC_RETURN_TYPES]:

    return rpc.robot.GetRobotJointsResponse(data=await get_robot_joints(req.args.robot_id))


@scene_needed
async def get_end_effector_pose_cb(req: rpc.robot.GetEndEffectorPoseRequest, ui: WsClient) -> \
        Union[rpc.robot.GetEndEffectorPoseResponse, hlp.RPC_RETURN_TYPES]:

    return rpc.robot.GetEndEffectorPoseResponse(data=await get_end_effector_pose(req.args.robot_id,
                                                                                 req.args.end_effector_id))


@scene_needed
async def get_end_effectors_cb(req: rpc.robot.GetEndEffectorsRequest, ui: WsClient) -> \
        Union[rpc.robot.GetEndEffectorsResponse, hlp.RPC_RETURN_TYPES]:

    return rpc.robot.GetEndEffectorsResponse(data=await get_end_effectors(req.args.robot_id))


@scene_needed
async def get_grippers_cb(req: rpc.robot.GetGrippersRequest, ui: WsClient) -> \
        Union[rpc.robot.GetGrippersResponse, hlp.RPC_RETURN_TYPES]:

    return rpc.robot.GetGrippersResponse(data=await get_grippers(req.args.robot_id))


@scene_needed
async def get_suctions_cb(req: rpc.robot.GetSuctionsRequest, ui: WsClient) -> \
        Union[rpc.robot.GetSuctionsResponse, hlp.RPC_RETURN_TYPES]:

    return rpc.robot.GetSuctionsResponse(data=await get_suctions(req.args.robot_id))


@scene_needed
async def register_for_joints_cb(req: rpc.robot.RegisterForJointsRequest, ui: WsClient) -> \
        Union[rpc.robot.RegisterForJointsResponse, hlp.RPC_RETURN_TYPES]:

    # TODO check if robot exists
    if req.args.send:

        if req.args.robot_id not in glob.ROBOT_JOINTS_REGISTERED_UIS:  # TODO use default dict
            glob.ROBOT_JOINTS_REGISTERED_UIS[req.args.robot_id] = set()

        glob.ROBOT_JOINTS_REGISTERED_UIS[req.args.robot_id].add(ui)

        if req.args.robot_id not in ROBOT_JOINTS_TASKS:
            ROBOT_JOINTS_TASKS[req.args.robot_id] = asyncio.create_task(robot_joints_event(req.args.robot_id))

    else:
        # TODO handle if ui is not registered
        glob.ROBOT_JOINTS_REGISTERED_UIS[req.args.robot_id].remove(ui)

        # TODO cancel task if not needed

    return None
