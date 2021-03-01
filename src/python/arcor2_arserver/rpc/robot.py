import asyncio
import time
from typing import Awaitable, Callable, Dict

from arcor2_calibration_data import client as calib_client
from arcor2_calibration_data.client import CalibrateRobotArgs
from websockets.server import WebSocketServerProtocol as WsClient

from arcor2 import transformations as tr
from arcor2 import ws_server
from arcor2.clients.persistent_storage import URL as ps_url
from arcor2.data import common
from arcor2.exceptions import Arcor2Exception
from arcor2.helpers import run_in_executor
from arcor2.object_types.abstract import Camera, Robot
from arcor2_arserver import camera
from arcor2_arserver import globals as glob
from arcor2_arserver import notifications as notif
from arcor2_arserver import objects_actions as osa
from arcor2_arserver import robot
from arcor2_arserver.decorators import project_needed, scene_needed
from arcor2_arserver.scene import ensure_scene_started, scene_started, update_scene_object_pose
from arcor2_arserver_data import events as sevts
from arcor2_arserver_data import rpc as srpc
from arcor2_arserver_data.events.common import ProcessState
from arcor2_arserver_data.events.robot import HandTeachingMode

RBT_CALIB = "RobotCalibration"

TaskDict = Dict[str, asyncio.Task]

ROBOT_JOINTS_TASKS: TaskDict = {}
EEF_POSE_TASKS: TaskDict = {}

EVENT_PERIOD = 0.1


async def robot_joints_event(robot_id: str) -> None:

    global ROBOT_JOINTS_TASKS

    glob.logger.info(f"Sending '{sevts.r.RobotJoints.__name__}' for robot '{robot_id}' started.")
    while scene_started() and glob.ROBOT_JOINTS_REGISTERED_UIS[robot_id]:

        start = time.monotonic()

        try:
            evt = sevts.r.RobotJoints(sevts.r.RobotJoints.Data(robot_id, (await robot.get_robot_joints(robot_id))))
        except Arcor2Exception as e:
            glob.logger.error(f"Failed to get joints for {robot_id}. {str(e)}")
            break

        evt_json = evt.to_json()
        await asyncio.gather(
            *[ws_server.send_json_to_client(ui, evt_json) for ui in glob.ROBOT_JOINTS_REGISTERED_UIS[robot_id]]
        )

        end = time.monotonic()
        await asyncio.sleep(EVENT_PERIOD - (end - start))

    del ROBOT_JOINTS_TASKS[robot_id]

    # TODO notify UIs that registration was cancelled
    del glob.ROBOT_JOINTS_REGISTERED_UIS[robot_id]

    glob.logger.info(f"Sending '{sevts.r.RobotJoints.__name__}' for robot '{robot_id}' stopped.")


async def eef_pose(robot_id: str, eef_id: str) -> sevts.r.RobotEef.Data.EefPose:

    return sevts.r.RobotEef.Data.EefPose(eef_id, (await robot.get_end_effector_pose(robot_id, eef_id)))


async def robot_eef_pose_event(robot_id: str) -> None:

    global EEF_POSE_TASKS

    glob.logger.info(f"Sending '{sevts.r.RobotEef.__name__}' for robot '{robot_id}' started.")

    while scene_started() and glob.ROBOT_EEF_REGISTERED_UIS[robot_id]:

        start = time.monotonic()

        evt = sevts.r.RobotEef(sevts.r.RobotEef.Data(robot_id))

        try:
            evt.data.end_effectors = await asyncio.gather(
                *[eef_pose(robot_id, eef_id) for eef_id in (await robot.get_end_effectors(robot_id))]
            )
        except Arcor2Exception as e:
            glob.logger.error(f"Failed to get eef pose for {robot_id}. {str(e)}")
            break

        evt_json = evt.to_json()
        await asyncio.gather(
            *[ws_server.send_json_to_client(ui, evt_json) for ui in glob.ROBOT_EEF_REGISTERED_UIS[robot_id]]
        )

        end = time.monotonic()
        await asyncio.sleep(EVENT_PERIOD - (end - start))

    del EEF_POSE_TASKS[robot_id]

    # TODO notify UIs that registration was cancelled
    del glob.ROBOT_EEF_REGISTERED_UIS[robot_id]

    glob.logger.info(f"Sending '{sevts.r.RobotEef.__name__}' for robot '{robot_id}' stopped.")


async def get_robot_meta_cb(req: srpc.r.GetRobotMeta.Request, ui: WsClient) -> srpc.r.GetRobotMeta.Response:

    return srpc.r.GetRobotMeta.Response(
        data=[obj.robot_meta for obj in glob.OBJECT_TYPES.values() if obj.robot_meta is not None]
    )


@scene_needed
async def get_robot_joints_cb(req: srpc.r.GetRobotJoints.Request, ui: WsClient) -> srpc.r.GetRobotJoints.Response:

    ensure_scene_started()
    return srpc.r.GetRobotJoints.Response(data=await robot.get_robot_joints(req.args.robot_id))


@scene_needed
async def get_end_effector_pose_cb(
    req: srpc.r.GetEndEffectorPose.Request, ui: WsClient
) -> srpc.r.GetEndEffectorPose.Response:

    ensure_scene_started()
    return srpc.r.GetEndEffectorPose.Response(
        data=await robot.get_end_effector_pose(req.args.robot_id, req.args.end_effector_id)
    )


@scene_needed
async def get_end_effectors_cb(req: srpc.r.GetEndEffectors.Request, ui: WsClient) -> srpc.r.GetEndEffectors.Response:

    ensure_scene_started()
    return srpc.r.GetEndEffectors.Response(data=await robot.get_end_effectors(req.args.robot_id))


@scene_needed
async def get_grippers_cb(req: srpc.r.GetGrippers.Request, ui: WsClient) -> srpc.r.GetGrippers.Response:

    ensure_scene_started()
    return srpc.r.GetGrippers.Response(data=await robot.get_grippers(req.args.robot_id))


@scene_needed
async def get_suctions_cb(req: srpc.r.GetSuctions.Request, ui: WsClient) -> srpc.r.GetSuctions.Response:

    ensure_scene_started()
    return srpc.r.GetSuctions.Response(data=await robot.get_suctions(req.args.robot_id))


async def register(
    req: srpc.r.RegisterForRobotEvent.Request,
    ui: WsClient,
    tasks: TaskDict,
    reg_uis: glob.RegisteredUiDict,
    coro: Callable[[str], Awaitable[None]],
) -> None:

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
async def register_for_robot_event_cb(req: srpc.r.RegisterForRobotEvent.Request, ui: WsClient) -> None:

    ensure_scene_started()

    # check if robot exists
    await osa.get_robot_instance(req.args.robot_id)

    if req.args.what == req.args.RegisterEnum.JOINTS:
        await register(req, ui, ROBOT_JOINTS_TASKS, glob.ROBOT_JOINTS_REGISTERED_UIS, robot_joints_event)
    elif req.args.what == req.args.RegisterEnum.EEF_POSE:

        if not (await robot.get_end_effectors(req.args.robot_id)):
            raise Arcor2Exception("Robot does not have any end effector.")

        await register(req, ui, EEF_POSE_TASKS, glob.ROBOT_EEF_REGISTERED_UIS, robot_eef_pose_event)
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
async def move_to_pose_cb(req: srpc.r.MoveToPose.Request, ui: WsClient) -> None:

    ensure_scene_started()
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
    asyncio.ensure_future(
        robot.move_to_pose(req.args.robot_id, req.args.end_effector_id, target_pose, req.args.speed, req.args.safe)
    )


@scene_needed
async def move_to_joints_cb(req: srpc.r.MoveToJoints.Request, ui: WsClient) -> None:

    ensure_scene_started()
    await check_feature(req.args.robot_id, Robot.move_to_joints.__name__)
    await robot.check_robot_before_move(req.args.robot_id)
    asyncio.ensure_future(robot.move_to_joints(req.args.robot_id, req.args.joints, req.args.speed, req.args.safe))


@scene_needed
async def stop_robot_cb(req: srpc.r.StopRobot.Request, ui: WsClient) -> None:

    ensure_scene_started()
    await check_feature(req.args.robot_id, Robot.stop.__name__)
    await robot.stop(req.args.robot_id)


@scene_needed
@project_needed
async def move_to_action_point_cb(req: srpc.r.MoveToActionPoint.Request, ui: WsClient) -> None:

    ensure_scene_started()
    await robot.check_robot_before_move(req.args.robot_id)

    assert glob.SCENE
    assert glob.PROJECT

    if (req.args.orientation_id is None) == (req.args.joints_id is None):
        raise Arcor2Exception("Set orientation or joints. Not both.")

    if req.args.orientation_id:

        await check_feature(req.args.robot_id, Robot.move_to_pose.__name__)

        if req.args.end_effector_id is None:
            raise Arcor2Exception("eef id has to be set.")

        pose = tr.abs_pose_from_ap_orientation(glob.SCENE, glob.PROJECT, req.args.orientation_id)

        # TODO check if the target pose is reachable (dry_run)
        asyncio.ensure_future(
            robot.move_to_ap_orientation(
                req.args.robot_id,
                req.args.end_effector_id,
                pose,
                req.args.speed,
                req.args.orientation_id,
                req.args.safe,
            )
        )

    elif req.args.joints_id:

        await check_feature(req.args.robot_id, Robot.move_to_joints.__name__)

        joints = glob.PROJECT.joints(req.args.joints_id)

        # TODO check if the joints are within limits and reachable (dry_run)
        asyncio.ensure_future(
            robot.move_to_ap_joints(req.args.robot_id, joints.joints, req.args.speed, req.args.joints_id, req.args.safe)
        )


@scene_needed
async def ik_cb(req: srpc.r.InverseKinematics.Request, ui: WsClient) -> srpc.r.InverseKinematics.Response:

    ensure_scene_started()
    await check_feature(req.args.robot_id, Robot.inverse_kinematics.__name__)

    joints = await robot.ik(
        req.args.robot_id, req.args.end_effector_id, req.args.pose, req.args.start_joints, req.args.avoid_collisions
    )
    resp = srpc.r.InverseKinematics.Response()
    resp.data = joints
    return resp


@scene_needed
async def fk_cb(req: srpc.r.ForwardKinematics.Request, ui: WsClient) -> srpc.r.ForwardKinematics.Response:

    ensure_scene_started()
    await check_feature(req.args.robot_id, Robot.forward_kinematics.__name__)

    pose = await robot.fk(req.args.robot_id, req.args.end_effector_id, req.args.joints)
    resp = srpc.r.ForwardKinematics.Response()
    resp.data = pose
    return resp


async def calibrate_robot(robot_inst: Robot, camera_inst: Camera, move_to_calibration_pose: bool) -> None:

    assert glob.SCENE
    assert camera_inst.color_camera_params

    # TODO it should not be possible to close the scene during this process

    await notif.broadcast_event(ProcessState(ProcessState.Data(RBT_CALIB, ProcessState.Data.StateEnum.Started)))

    try:

        if move_to_calibration_pose:
            await run_in_executor(robot_inst.move_to_calibration_pose)
        robot_joints = await run_in_executor(robot_inst.robot_joints)
        depth_image = await run_in_executor(camera_inst.depth_image, 128)

        args = CalibrateRobotArgs(
            robot_joints,
            robot_inst.pose,
            camera_inst.pose,
            camera_inst.color_camera_params,
            f"{ps_url}/models/{robot_inst.urdf_package_name}/mesh/file",
        )

        new_pose = await run_in_executor(calib_client.calibrate_robot, args, depth_image)

    except Arcor2Exception as e:
        await notif.broadcast_event(
            ProcessState(ProcessState.Data(RBT_CALIB, ProcessState.Data.StateEnum.Failed, str(e)))
        )
        glob.logger.exception("Failed to calibrate the robot.")
        return

    await update_scene_object_pose(glob.SCENE.object(robot_inst.id), new_pose, robot_inst)
    await notif.broadcast_event(ProcessState(ProcessState.Data(RBT_CALIB, ProcessState.Data.StateEnum.Finished)))


@scene_needed
async def calibrate_robot_cb(req: srpc.r.CalibrateRobot.Request, ui: WsClient) -> None:

    ensure_scene_started()
    robot_inst = await osa.get_robot_instance(req.args.robot_id)

    if not robot_inst.urdf_package_name:
        raise Arcor2Exception("Robot with model required!")

    if req.args.camera_id:
        camera_inst = camera.get_camera_instance(req.args.camera_id)
    else:
        for obj in glob.SCENE_OBJECT_INSTANCES.values():
            if isinstance(obj, Camera):
                camera_inst = obj
                break
        else:
            raise Arcor2Exception("No camera found.")

    if camera_inst.color_camera_params is None:
        raise Arcor2Exception("Calibrated camera required!")

    # TODO check camera features / check that it supports depth
    asyncio.ensure_future(calibrate_robot(robot_inst, camera_inst, req.args.move_to_calibration_pose))

    return None


@scene_needed
async def hand_teaching_mode_cb(req: srpc.r.HandTeachingMode.Request, ui: WsClient) -> None:

    ensure_scene_started()
    robot_inst = await osa.get_robot_instance(req.args.robot_id)

    otd = osa.get_obj_type_data(req.args.robot_id)
    assert otd.robot_meta is not None
    if not otd.robot_meta.features.hand_teaching:
        raise Arcor2Exception("Robot does not support hand teaching.")

    hand_teaching_mode = await run_in_executor(robot_inst.get_hand_teaching_mode)

    if req.args.enable == hand_teaching_mode:
        raise Arcor2Exception("That's the current state.")

    if req.dry_run:
        return

    await run_in_executor(robot_inst.set_hand_teaching_mode, req.args.enable)
    evt = HandTeachingMode(HandTeachingMode.Data(req.args.robot_id, req.args.enable))
    asyncio.ensure_future(notif.broadcast_event(evt))
