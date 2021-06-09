import asyncio
import math
import time
from typing import Awaitable, Callable, Dict, List, Optional

import numpy as np
from arcor2_calibration_data import client as calib_client
from arcor2_calibration_data.client import CalibrateRobotArgs
from websockets.server import WebSocketServerProtocol as WsClient

from arcor2 import transformations as tr
from arcor2 import ws_server
from arcor2.clients.project_service import URL as ps_url
from arcor2.data import common
from arcor2.exceptions import Arcor2Exception
from arcor2.helpers import run_in_executor
from arcor2.object_types.abstract import Camera, Robot
from arcor2_arserver import camera
from arcor2_arserver import globals as glob
from arcor2_arserver import notifications as notif
from arcor2_arserver import objects_actions as osa
from arcor2_arserver import robot
from arcor2_arserver.helpers import ctx_read_lock, ctx_write_lock, ensure_locked
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


async def robot_joints_event(robot_inst: Robot) -> None:

    global ROBOT_JOINTS_TASKS

    glob.logger.info(f"Sending '{sevts.r.RobotJoints.__name__}' for robot '{robot_inst.id}' started.")
    while scene_started() and glob.ROBOT_JOINTS_REGISTERED_UIS[robot_inst.id]:

        start = time.monotonic()

        try:
            evt = sevts.r.RobotJoints(
                sevts.r.RobotJoints.Data(robot_inst.id, (await robot.get_robot_joints(robot_inst)))
            )
        except Arcor2Exception as e:
            glob.logger.error(f"Failed to get joints for {robot_inst.id}. {str(e)}")
            break

        evt_json = evt.to_json()
        await asyncio.gather(
            *[ws_server.send_json_to_client(ui, evt_json) for ui in glob.ROBOT_JOINTS_REGISTERED_UIS[robot_inst.id]]
        )

        end = time.monotonic()
        await asyncio.sleep(EVENT_PERIOD - (end - start))

    del ROBOT_JOINTS_TASKS[robot_inst.id]

    # TODO notify UIs that registration was cancelled
    del glob.ROBOT_JOINTS_REGISTERED_UIS[robot_inst.id]

    glob.logger.info(f"Sending '{sevts.r.RobotJoints.__name__}' for robot '{robot_inst.id}' stopped.")


async def eef_pose(robot_inst: Robot, eef_id: str) -> sevts.r.RobotEef.Data.EefPose:

    return sevts.r.RobotEef.Data.EefPose(eef_id, (await robot.get_end_effector_pose(robot_inst, eef_id)))


async def robot_eef_pose_event(robot_inst: Robot) -> None:

    global EEF_POSE_TASKS

    glob.logger.info(f"Sending '{sevts.r.RobotEef.__name__}' for robot '{robot_inst.id}' started.")

    while scene_started() and glob.ROBOT_EEF_REGISTERED_UIS[robot_inst.id]:

        start = time.monotonic()

        evt = sevts.r.RobotEef(sevts.r.RobotEef.Data(robot_inst.id))

        try:
            evt.data.end_effectors = await asyncio.gather(
                *[eef_pose(robot_inst, eef_id) for eef_id in (await robot.get_end_effectors(robot_inst))]
            )
        except Arcor2Exception as e:
            glob.logger.error(f"Failed to get eef pose for {robot_inst.id}. {str(e)}")
            break

        evt_json = evt.to_json()
        await asyncio.gather(
            *[ws_server.send_json_to_client(ui, evt_json) for ui in glob.ROBOT_EEF_REGISTERED_UIS[robot_inst.id]]
        )

        end = time.monotonic()
        await asyncio.sleep(EVENT_PERIOD - (end - start))

    del EEF_POSE_TASKS[robot_inst.id]

    # TODO notify UIs that registration was cancelled
    del glob.ROBOT_EEF_REGISTERED_UIS[robot_inst.id]

    glob.logger.info(f"Sending '{sevts.r.RobotEef.__name__}' for robot '{robot_inst.id}' stopped.")


async def get_robot_meta_cb(req: srpc.r.GetRobotMeta.Request, ui: WsClient) -> srpc.r.GetRobotMeta.Response:

    return srpc.r.GetRobotMeta.Response(
        data=[obj.robot_meta for obj in glob.OBJECT_TYPES.values() if obj.robot_meta is not None]
    )


async def get_robot_joints_cb(req: srpc.r.GetRobotJoints.Request, ui: WsClient) -> srpc.r.GetRobotJoints.Response:

    glob.LOCK.scene_or_exception()

    async with ctx_read_lock(req.args.robot_id, glob.USERS.user_name(ui)):
        ensure_scene_started()
        return srpc.r.GetRobotJoints.Response(
            data=await robot.get_robot_joints(await osa.get_robot_instance(req.args.robot_id))
        )


async def get_end_effector_pose_cb(
    req: srpc.r.GetEndEffectorPose.Request, ui: WsClient
) -> srpc.r.GetEndEffectorPose.Response:

    glob.LOCK.scene_or_exception()

    async with ctx_read_lock(req.args.robot_id, glob.USERS.user_name(ui)):
        ensure_scene_started()
        return srpc.r.GetEndEffectorPose.Response(
            data=await robot.get_end_effector_pose(
                await osa.get_robot_instance(req.args.robot_id), req.args.end_effector_id
            )
        )


async def get_end_effectors_cb(req: srpc.r.GetEndEffectors.Request, ui: WsClient) -> srpc.r.GetEndEffectors.Response:

    glob.LOCK.scene_or_exception()

    async with ctx_read_lock(req.args.robot_id, glob.USERS.user_name(ui)):
        ensure_scene_started()
        return srpc.r.GetEndEffectors.Response(
            data=await robot.get_end_effectors(await osa.get_robot_instance(req.args.robot_id))
        )


async def get_grippers_cb(req: srpc.r.GetGrippers.Request, ui: WsClient) -> srpc.r.GetGrippers.Response:

    glob.LOCK.scene_or_exception()

    async with ctx_read_lock(req.args.robot_id, glob.USERS.user_name(ui)):
        ensure_scene_started()
        return srpc.r.GetGrippers.Response(
            data=await robot.get_grippers(await osa.get_robot_instance(req.args.robot_id))
        )


async def get_suctions_cb(req: srpc.r.GetSuctions.Request, ui: WsClient) -> srpc.r.GetSuctions.Response:

    glob.LOCK.scene_or_exception()

    async with ctx_read_lock(req.args.robot_id, glob.USERS.user_name(ui)):
        ensure_scene_started()
        return srpc.r.GetSuctions.Response(
            data=await robot.get_suctions(await osa.get_robot_instance(req.args.robot_id))
        )


async def register(
    req: srpc.r.RegisterForRobotEvent.Request,
    robot_inst: Robot,
    ui: WsClient,
    tasks: TaskDict,
    reg_uis: glob.RegisteredUiDict,
    coro: Callable[[Robot], Awaitable[None]],
) -> None:

    if req.args.send:

        reg_uis[req.args.robot_id].add(ui)

        if req.args.robot_id not in tasks:
            # start task
            tasks[req.args.robot_id] = asyncio.create_task(coro(robot_inst))

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


async def register_for_robot_event_cb(req: srpc.r.RegisterForRobotEvent.Request, ui: WsClient) -> None:

    glob.LOCK.scene_or_exception()

    async with ctx_read_lock(req.args.robot_id, glob.USERS.user_name(ui)):
        ensure_scene_started()

        # check if robot exists
        robot_inst = await osa.get_robot_instance(req.args.robot_id)

        if req.args.what == req.args.RegisterEnum.JOINTS:
            await register(
                req, robot_inst, ui, ROBOT_JOINTS_TASKS, glob.ROBOT_JOINTS_REGISTERED_UIS, robot_joints_event
            )
        elif req.args.what == req.args.RegisterEnum.EEF_POSE:

            if not (await robot.get_end_effectors(robot_inst)):
                raise Arcor2Exception("Robot does not have any end effector.")

            await register(req, robot_inst, ui, EEF_POSE_TASKS, glob.ROBOT_EEF_REGISTERED_UIS, robot_eef_pose_event)
        else:
            raise Arcor2Exception(f"Option '{req.args.what.value}' not implemented.")

        return None


async def check_feature(robot_inst: Robot, feature_name: str) -> None:

    obj_type = glob.OBJECT_TYPES[robot_inst.__class__.__name__]

    if obj_type.robot_meta is None:
        raise Arcor2Exception("Not a robot.")

    try:
        if not getattr(obj_type.robot_meta.features, feature_name):
            raise Arcor2Exception(f"Robot does not support '{feature_name}' feature.")
    except AttributeError:
        raise Arcor2Exception(f"Unknown robot feature: {feature_name}.")


async def move_to_pose_cb(req: srpc.r.MoveToPose.Request, ui: WsClient) -> None:

    glob.LOCK.scene_or_exception()
    user_name = glob.USERS.user_name(ui)

    async with ctx_write_lock(req.args.robot_id, user_name, auto_unlock=False):
        ensure_scene_started()

        robot_inst = await osa.get_robot_instance(req.args.robot_id, req.args.end_effector_id)

        await check_feature(robot_inst, Robot.move_to_pose.__name__)
        await robot.check_robot_before_move(robot_inst)

        if (req.args.position is None) != (req.args.orientation is None):

            target_pose = await robot.get_end_effector_pose(robot_inst, req.args.end_effector_id)

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
            robot.move_to_pose(
                robot_inst,
                req.args.end_effector_id,
                target_pose,
                req.args.speed,
                req.args.safe,
                user_name,
            )
        )


async def move_to_joints_cb(req: srpc.r.MoveToJoints.Request, ui: WsClient) -> None:

    glob.LOCK.scene_or_exception()
    user_name = glob.USERS.user_name(ui)

    async with ctx_write_lock(req.args.robot_id, user_name, auto_unlock=False):

        ensure_scene_started()
        robot_inst = await osa.get_robot_instance(req.args.robot_id)
        await check_feature(robot_inst, Robot.move_to_joints.__name__)
        await robot.check_robot_before_move(robot_inst)

        asyncio.ensure_future(
            robot.move_to_joints(robot_inst, req.args.joints, req.args.speed, req.args.safe, user_name)
        )


async def stop_robot_cb(req: srpc.r.StopRobot.Request, ui: WsClient) -> None:

    glob.LOCK.scene_or_exception()

    # Stop robot cannot use lock, because robot is locked when action is called. Stop will also release lock.
    ensure_scene_started()
    robot_inst = await osa.get_robot_instance(req.args.robot_id)
    await check_feature(robot_inst, Robot.stop.__name__)
    await robot.stop(robot_inst)


async def move_to_action_point_cb(req: srpc.r.MoveToActionPoint.Request, ui: WsClient) -> None:

    scene = glob.LOCK.scene_or_exception()
    project = glob.LOCK.project_or_exception()

    async with ctx_write_lock(req.args.robot_id, glob.USERS.user_name(ui)):

        ensure_scene_started()
        robot_inst = await osa.get_robot_instance(req.args.robot_id)

        await robot.check_robot_before_move(robot_inst)

        if (req.args.orientation_id is None) == (req.args.joints_id is None):
            raise Arcor2Exception("Set orientation or joints. Not both.")

        if req.args.orientation_id:

            await check_feature(robot_inst, Robot.move_to_pose.__name__)

            if req.args.end_effector_id is None:
                raise Arcor2Exception("eef id has to be set.")

            pose = tr.abs_pose_from_ap_orientation(scene, project, req.args.orientation_id)

            # TODO check if the target pose is reachable (dry_run)
            asyncio.ensure_future(
                robot.move_to_ap_orientation(
                    robot_inst,
                    req.args.end_effector_id,
                    pose,
                    req.args.speed,
                    req.args.orientation_id,
                    req.args.safe,
                )
            )

        elif req.args.joints_id:

            await check_feature(robot_inst, Robot.move_to_joints.__name__)

            joints = project.joints(req.args.joints_id)

            # TODO check if the joints are within limits and reachable (dry_run)
            asyncio.ensure_future(
                robot.move_to_ap_joints(robot_inst, joints.joints, req.args.speed, req.args.joints_id, req.args.safe)
            )


async def ik_cb(req: srpc.r.InverseKinematics.Request, ui: WsClient) -> srpc.r.InverseKinematics.Response:

    glob.LOCK.scene_or_exception()

    async with ctx_read_lock([req.args.robot_id, req.args.end_effector_id], glob.USERS.user_name(ui)):

        ensure_scene_started()
        robot_inst = await osa.get_robot_instance(req.args.robot_id)
        await check_feature(robot_inst, Robot.inverse_kinematics.__name__)

        joints = await robot.ik(
            robot_inst, req.args.end_effector_id, req.args.pose, req.args.start_joints, req.args.avoid_collisions
        )
        resp = srpc.r.InverseKinematics.Response()
        resp.data = joints
        return resp


async def fk_cb(req: srpc.r.ForwardKinematics.Request, ui: WsClient) -> srpc.r.ForwardKinematics.Response:

    glob.LOCK.scene_or_exception()

    async with ctx_read_lock([req.args.robot_id, req.args.end_effector_id], glob.USERS.user_name(ui)):

        ensure_scene_started()
        robot_inst = await osa.get_robot_instance(req.args.robot_id)
        await check_feature(robot_inst, Robot.forward_kinematics.__name__)

        pose = await robot.fk(robot_inst, req.args.end_effector_id, req.args.joints)
        resp = srpc.r.ForwardKinematics.Response()
        resp.data = pose
        return resp


async def calibrate_robot(robot_inst: Robot, camera_inst: Camera, move_to_calibration_pose: bool, ui: WsClient) -> None:

    try:
        scene = glob.LOCK.scene_or_exception()

        assert camera_inst.color_camera_params

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

        await update_scene_object_pose(scene, scene.object(robot_inst.id), new_pose, robot_inst)
        await notif.broadcast_event(ProcessState(ProcessState.Data(RBT_CALIB, ProcessState.Data.StateEnum.Finished)))
    finally:
        await glob.LOCK.write_unlock(camera_inst.id, glob.USERS.user_name(ui))


async def calibrate_robot_cb(req: srpc.r.CalibrateRobot.Request, ui: WsClient) -> None:

    glob.LOCK.scene_or_exception()

    async with ctx_write_lock(req.args.camera_id, glob.USERS.user_name(ui), auto_unlock=False):
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

        await ensure_locked(req.args.robot_id, ui)

        asyncio.ensure_future(calibrate_robot(robot_inst, camera_inst, req.args.move_to_calibration_pose, ui))

        return None


async def hand_teaching_mode_cb(req: srpc.r.HandTeachingMode.Request, ui: WsClient) -> None:

    glob.LOCK.scene_or_exception()

    ensure_scene_started()
    robot_inst = await osa.get_robot_instance(req.args.robot_id)

    # in this case, method name does not correspond to feature name
    await check_feature(robot_inst, "hand_teaching")

    hand_teaching_mode = await run_in_executor(robot_inst.get_hand_teaching_mode)

    if req.args.enable == hand_teaching_mode:
        raise Arcor2Exception("That's the current state.")

    await ensure_locked(req.args.robot_id, ui)

    if req.dry_run:
        return

    await run_in_executor(robot_inst.set_hand_teaching_mode, req.args.enable)
    evt = HandTeachingMode(HandTeachingMode.Data(req.args.robot_id, req.args.enable))
    asyncio.ensure_future(notif.broadcast_event(evt))


async def step_robot_eef_cb(req: srpc.r.StepRobotEef.Request, ui: WsClient) -> None:

    scene = glob.LOCK.scene_or_exception()

    ensure_scene_started()
    robot_inst = await osa.get_robot_instance(req.args.robot_id)

    await check_feature(robot_inst, Robot.move_to_pose.__name__)
    await robot.check_robot_before_move(robot_inst)

    tp = await robot.get_end_effector_pose(robot_inst, req.args.end_effector_id)

    if req.args.mode == req.args.mode.ROBOT:
        tp = tr.make_pose_rel(robot_inst.pose, tp)
    elif req.args.mode == req.args.mode.RELATIVE:
        assert req.args.pose
        tp = tr.make_pose_rel(req.args.pose, tp)
    elif req.args.mode == req.args.mode.USER:
        assert req.args.pose
        raise Arcor2Exception("Not supported yet.")

    if req.args.what == req.args.what.POSITION:
        if req.args.axis == req.args.axis.X:
            tp.position.x += req.args.step
        elif req.args.axis == req.args.axis.Y:
            tp.position.y += req.args.step
        elif req.args.axis == req.args.axis.Z:
            tp.position.z += req.args.step
    elif req.args.what == req.args.what.ORIENTATION:
        if req.args.axis == req.args.axis.X:
            tp.orientation *= common.Orientation.from_rotation_vector(x=req.args.step)
        elif req.args.axis == req.args.axis.Y:
            tp.orientation *= common.Orientation.from_rotation_vector(y=req.args.step)
        elif req.args.axis == req.args.axis.Z:
            tp.orientation *= common.Orientation.from_rotation_vector(z=req.args.step)

    if req.args.mode == req.args.mode.ROBOT:
        tp = tr.make_pose_abs(robot_inst.pose, tp)
    elif req.args.mode == req.args.mode.RELATIVE:
        assert req.args.pose
        tp = tr.make_pose_abs(req.args.pose, tp)

    await robot.check_reachability(scene, robot_inst, req.args.end_effector_id, tp, req.args.safe)

    await ensure_locked(req.args.robot_id, ui)

    if req.dry_run:
        return

    asyncio.ensure_future(robot.move_to_pose(robot_inst, req.args.end_effector_id, tp, req.args.speed, req.args.safe))


async def set_eef_perpendicular_to_world_cb(req: srpc.r.SetEefPerpendicularToWorld.Request, ui: WsClient) -> None:

    glob.LOCK.scene_or_exception()

    ensure_scene_started()
    robot_inst = await osa.get_robot_instance(req.args.robot_id)

    await check_feature(robot_inst, Robot.move_to_pose.__name__)
    await check_feature(robot_inst, Robot.inverse_kinematics.__name__)
    await robot.check_robot_before_move(robot_inst)

    await ensure_locked(req.args.robot_id, ui)

    if req.dry_run:  # attempt to find suitable joints can take some time so it is not done for dry_run
        return

    tp, current_joints = await robot.get_pose_and_joints(robot_inst, req.args.end_effector_id)

    target_joints: Optional[List[common.Joint]] = None
    target_joints_diff: float = 0.0

    # select best (closest joint configuration) reachable pose
    tasks = [
        robot.ik(robot_inst, req.args.end_effector_id, pose, current_joints, req.args.safe)
        for pose in [
            common.Pose(
                tp.position,
                common.Orientation.from_rotation_vector(y=math.pi) * common.Orientation.from_rotation_vector(z=z_rot),
            )
            for z_rot in np.linspace(-math.pi, math.pi, 360)
        ]
    ]

    for res in await asyncio.gather(*tasks, return_exceptions=True):

        if not isinstance(res, list):
            continue

        if not target_joints:
            target_joints = res
            for f, b in zip(current_joints, target_joints):
                assert f.name == b.name
                target_joints_diff += (f.value - b.value) ** 2
        else:
            diff = 0.0
            for f, b in zip(current_joints, res):
                assert f.name == b.name
                diff += (f.value - b.value) ** 2

            if diff < target_joints_diff:
                target_joints = res
                target_joints_diff = diff

    if not target_joints:
        raise Arcor2Exception("Could not find reachable pose.")

    asyncio.ensure_future(robot.move_to_joints(robot_inst, target_joints, req.args.speed, req.args.safe))
