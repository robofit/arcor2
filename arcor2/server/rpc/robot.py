import asyncio
import time
from typing import Dict, Callable, Awaitable

from websockets.server import WebSocketServerProtocol as WsClient

from arcor2.data import rpc, events
from arcor2.exceptions import Arcor2Exception
from arcor2 import helpers as hlp

from arcor2.server import globals as glob, objects_services_actions as osa, robot
from arcor2.server.decorators import scene_needed

TaskDict = Dict[str, asyncio.Task]

ROBOT_JOINTS_TASKS: TaskDict = {}
EEF_POSE_TASKS: TaskDict = {}

EVENT_PERIOD = 0.1


async def robot_joints_event(robot_id: str) -> None:

    global ROBOT_JOINTS_TASKS

    await glob.logger.info(f"Sending '{events.RobotJointsEvent.__name__}' for robot '{robot_id}' started.")
    while glob.SCENE and glob.ROBOT_JOINTS_REGISTERED_UIS[robot_id]:

        start = time.monotonic()

        evt = events.RobotJointsEvent()

        try:
            evt.data = events.RobotJointsData(robot_id, (await robot.get_robot_joints(robot_id)))
        except Arcor2Exception as e:
            glob.logger.error(f"Failed to get joints for {robot_id}. {e.message}")
            break

        evt_json = evt.to_json()
        await asyncio.gather(*[hlp.send_json_to_client(ui, evt_json)
                               for ui in glob.ROBOT_JOINTS_REGISTERED_UIS[robot_id]])

        end = time.monotonic()
        await asyncio.sleep(EVENT_PERIOD-(end-start))

    del ROBOT_JOINTS_TASKS[robot_id]

    # TODO notify UIs that registration was cancelled
    del glob.ROBOT_JOINTS_REGISTERED_UIS[robot_id]

    await glob.logger.info(f"Sending '{events.RobotJointsEvent.__name__}' for robot '{robot_id}' stopped.")


async def eef_pose(robot_id: str, eef_id: str) -> events.EefPose:

    return events.EefPose(eef_id, (await robot.get_end_effector_pose(robot_id, eef_id)))


async def robot_eef_pose_event(robot_id: str) -> None:

    global EEF_POSE_TASKS

    await glob.logger.info(f"Sending '{events.RobotEefEvent.__name__}' for robot '{robot_id}' started.")

    while glob.SCENE and glob.ROBOT_EEF_REGISTERED_UIS[robot_id]:

        start = time.monotonic()

        evt = events.RobotEefEvent()
        evt.data = events.RobotEefData(robot_id)

        try:
            evt.data.end_effectors = await asyncio.gather(
                *[eef_pose(robot_id, eef_id) for eef_id in (await robot.get_end_effectors(robot_id))])
        except Arcor2Exception as e:
            glob.logger.error(f"Failed to get eef pose for {robot_id}. {e.message}")
            break

        evt_json = evt.to_json()
        await asyncio.gather(*[hlp.send_json_to_client(ui, evt_json) for ui in glob.ROBOT_EEF_REGISTERED_UIS[robot_id]])

        end = time.monotonic()
        await asyncio.sleep(EVENT_PERIOD-(end-start))

    del EEF_POSE_TASKS[robot_id]

    # TODO notify UIs that registration was cancelled
    del glob.ROBOT_EEF_REGISTERED_UIS[robot_id]

    await glob.logger.info(f"Sending '{events.RobotEefEvent.__name__}' for robot '{robot_id}' stopped.")


async def get_robot_meta_cb(req: rpc.robot.GetRobotMetaRequest, ui: WsClient) ->\
        rpc.robot.GetRobotMetaResponse:

    return rpc.robot.GetRobotMetaResponse(data=list(glob.ROBOT_META.values()))


@scene_needed
async def get_robot_joints_cb(req: rpc.robot.GetRobotJointsRequest, ui: WsClient) -> \
        rpc.robot.GetRobotJointsResponse:

    return rpc.robot.GetRobotJointsResponse(data=await robot.get_robot_joints(req.args.robot_id))


@scene_needed
async def get_end_effector_pose_cb(req: rpc.robot.GetEndEffectorPoseRequest, ui: WsClient) -> \
        rpc.robot.GetEndEffectorPoseResponse:

    return rpc.robot.GetEndEffectorPoseResponse(
        data=await robot.get_end_effector_pose(req.args.robot_id, req.args.end_effector_id))


@scene_needed
async def get_end_effectors_cb(req: rpc.robot.GetEndEffectorsRequest, ui: WsClient) -> \
        rpc.robot.GetEndEffectorsResponse:

    return rpc.robot.GetEndEffectorsResponse(data=await robot.get_end_effectors(req.args.robot_id))


@scene_needed
async def get_grippers_cb(req: rpc.robot.GetGrippersRequest, ui: WsClient) -> \
        rpc.robot.GetGrippersResponse:

    return rpc.robot.GetGrippersResponse(data=await robot.get_grippers(req.args.robot_id))


@scene_needed
async def get_suctions_cb(req: rpc.robot.GetSuctionsRequest, ui: WsClient) -> \
        rpc.robot.GetSuctionsResponse:

    return rpc.robot.GetSuctionsResponse(data=await robot.get_suctions(req.args.robot_id))


async def register(req: rpc.robot.RegisterForRobotEventRequest, ui: WsClient, tasks: TaskDict,
                   reg_uis: glob.RegisteredUiDict, coro: Callable[[str], Awaitable[None]]) -> None:

    if req.args.send:

        reg_uis[req.args.robot_id].add(ui)

        if req.args.robot_id not in tasks:
            # start task
            tasks[req.args.robot_id] = asyncio.create_task(coro(req.args.robot_id))

    else:
        try:
            reg_uis[req.args.robot_id].remove(ui)
        except KeyError as e:
            raise Arcor2Exception("Failed to unregister.") from e

        # cancel task if not needed anymore
        if not reg_uis[req.args.robot_id]:
            task = tasks[req.args.robot_id]

            if not task.cancelled():
                task.cancel()

            del tasks[req.args.robot_id]


@scene_needed
async def register_for_robot_event_cb(req: rpc.robot.RegisterForRobotEventRequest, ui: WsClient) -> None:

    # check if robot exists
    await osa.get_robot_instance(req.args.robot_id)

    if req.args.what == rpc.robot.RegisterEnum.JOINTS:
        await register(req, ui, ROBOT_JOINTS_TASKS, glob.ROBOT_JOINTS_REGISTERED_UIS,
                       robot_joints_event)
    elif req.args.what == rpc.robot.RegisterEnum.EEF_POSE:

        if not (await robot.get_end_effectors(req.args.robot_id)):
            raise Arcor2Exception("Robot does not have any end effector.")

        await register(req, ui, EEF_POSE_TASKS, glob.ROBOT_EEF_REGISTERED_UIS,
                       robot_eef_pose_event)
    else:
        raise Arcor2Exception(f"Option '{req.args.what.value}' not implemented.")

    return None
