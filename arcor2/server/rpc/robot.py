import asyncio
import time
from typing import Awaitable, Callable, Dict

from websockets.server import WebSocketServerProtocol as WsClient

from arcor2 import helpers as hlp
from arcor2.data import common, events, rpc
from arcor2.exceptions import Arcor2Exception
from arcor2.object_types.abstract import Robot
from arcor2.server import globals as glob, objects_services_actions as osa, robot
from arcor2.server.decorators import project_needed, scene_needed

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
        await asyncio.sleep(EVENT_PERIOD - (end - start))

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
        await asyncio.sleep(EVENT_PERIOD - (end - start))

    del EEF_POSE_TASKS[robot_id]

    # TODO notify UIs that registration was cancelled
    del glob.ROBOT_EEF_REGISTERED_UIS[robot_id]

    await glob.logger.info(f"Sending '{events.RobotEefEvent.__name__}' for robot '{robot_id}' stopped.")


async def get_robot_meta_cb(req: rpc.robot.GetRobotMetaRequest, ui: WsClient) ->\
        rpc.robot.GetRobotMetaResponse:

    return rpc.robot.GetRobotMetaResponse(
        data=[obj.robot_meta for obj in glob.OBJECT_TYPES.values() if obj.robot_meta is not None]
    )


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


async def check_feature(robot_id: str, feature_name: str) -> None:

    obj_type = glob.OBJECT_TYPES[(await osa.get_robot_instance(robot_id)).__class__.__name__]

    if obj_type.robot_meta is None:
        raise Arcor2Exception("Not a robot.")

    if not getattr(obj_type.robot_meta.features, feature_name):
        raise Arcor2Exception(f"Robot does not support '{feature_name}' feature.")


@scene_needed
async def move_to_pose_cb(req: rpc.robot.MoveToPoseRequest, ui: WsClient) -> None:

    await check_feature(req.args.robot_id, Robot.move_to_pose.__name__)
    await robot.check_robot_before_move(req.args.robot_id)

    if (req.args.position is None) != (req.args.orientation is None):

        target_pose = await robot.get_end_effector_pose(req.args.robot_id, req.args.end_effector_id)

        if req.args.position:
            target_pose.position = req.args.position
        elif req.args.orientation:
            target_pose.orientation = req.args.orientation

    elif req.args.position is not None and req.args.orientation is not None:
        target_pose = common.Pose(req.args.position, req.args.orientation)
    else:
        raise Arcor2Exception("Position or orientation should be given.")

    # TODO check if the target pose is reachable (dry_run)
    asyncio.ensure_future(robot.move_to_pose(req.args.robot_id, req.args.end_effector_id, target_pose, req.args.speed))


@scene_needed
async def move_to_joints_cb(req: rpc.robot.MoveToJointsRequest, ui: WsClient) -> None:

    await check_feature(req.args.robot_id, Robot.move_to_joints.__name__)
    await robot.check_robot_before_move(req.args.robot_id)
    asyncio.ensure_future(robot.move_to_joints(req.args.robot_id, req.args.joints, req.args.speed))


@scene_needed
async def stop_robot_cb(req: rpc.robot.StopRobotRequest, ui: WsClient) -> None:

    await check_feature(req.args.robot_id, Robot.stop.__name__)
    await robot.stop(req.args.robot_id)


@scene_needed
@project_needed
async def move_to_action_point_cb(req: rpc.robot.MoveToActionPointRequest, ui: WsClient) -> None:

    await robot.check_robot_before_move(req.args.robot_id)

    assert glob.PROJECT

    # TODO check RobotMeta if the robot supports this

    if (req.args.orientation_id is None) == (req.args.joints_id is None):
        raise Arcor2Exception("Set orientation or joints. Not both.")

    if req.args.orientation_id:

        await check_feature(req.args.robot_id, Robot.move_to_pose.__name__)

        if req.args.end_effector_id is None:
            raise Arcor2Exception("eef id has to be set.")

        pose = glob.PROJECT.pose(req.args.orientation_id)

        # TODO check if the target pose is reachable (dry_run)
        asyncio.ensure_future(robot.move_to_ap_orientation(
            req.args.robot_id, req.args.end_effector_id, pose, req.args.speed, req.args.orientation_id))

    elif req.args.joints_id:

        await check_feature(req.args.robot_id, Robot.move_to_joints.__name__)

        joints = glob.PROJECT.joints(req.args.joints_id)

        # TODO check if the joints are within limits and reachable (dry_run)
        asyncio.ensure_future(robot.move_to_ap_joints(
            req.args.robot_id, joints.joints, req.args.speed, req.args.joints_id))
