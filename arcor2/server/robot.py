import inspect
import os
from typing import List, Set, Type

from typed_ast.ast3 import AST

import arcor2.helpers as hlp
from arcor2.data import common, events, robot
from arcor2.exceptions import Arcor2Exception
from arcor2.object_types import utils as otu
from arcor2.object_types.abstract import Robot
from arcor2.server import globals as glob, notifications as notif, objects_actions as osa
from arcor2.source.utils import function_implemented


class RobotPoseException(Arcor2Exception):
    pass


async def get_end_effectors(robot_id: str) -> Set[str]:
    """
    :param robot_id:
    :return: IDs of existing end effectors.
    """

    robot_inst = await osa.get_robot_instance(robot_id)
    return await hlp.run_in_executor(robot_inst.get_end_effectors_ids)


async def get_grippers(robot_id: str) -> Set[str]:
    """
    :param robot_id:
    :return: IDs of existing grippers.
    """

    robot_inst = await osa.get_robot_instance(robot_id)
    return await hlp.run_in_executor(robot_inst.grippers)


async def get_suctions(robot_id: str) -> Set[str]:
    """
    :param robot_id:
    :return: IDs of existing suctions.
    """

    robot_inst = await osa.get_robot_instance(robot_id)
    return await hlp.run_in_executor(robot_inst.suctions)


async def get_end_effector_pose(robot_id: str, end_effector: str) -> common.Pose:
    """
    :param robot_id:
    :param end_effector:
    :return: Global pose
    """

    robot_inst = await osa.get_robot_instance(robot_id, end_effector)
    return await hlp.run_in_executor(robot_inst.get_end_effector_pose, end_effector)


async def get_robot_joints(robot_id: str) -> List[common.Joint]:
    """
    :param robot_id:
    :return: List of joints
    """

    robot_inst = await osa.get_robot_instance(robot_id)
    return await hlp.run_in_executor(robot_inst.robot_joints)


def feature(tree: AST, robot_type: Type[Robot], func_name: str) -> bool:

    if not function_implemented(tree, func_name):
        return False

    sign = inspect.signature(getattr(robot_type, func_name))
    return inspect.signature(getattr(Robot, func_name)) == sign


def _feature(type_def: Type[Robot], method_name: str) -> bool:

    assert glob.OBJECT_TYPES

    method = getattr(type_def, method_name)
    where_it_is_defined = glob.OBJECT_TYPES[method.__qualname__.split(".")[0]]

    if where_it_is_defined.type_def is Robot or where_it_is_defined.meta.disabled:
        return False

    assert where_it_is_defined.ast is not None
    assert where_it_is_defined.type_def is not None
    assert issubclass(where_it_is_defined.type_def, Robot)

    return feature(where_it_is_defined.ast, where_it_is_defined.type_def, method_name)


async def get_robot_meta(obj_type: otu.ObjectTypeData) -> None:

    if obj_type.meta.disabled:
        raise Arcor2Exception("Disabled object type.")

    assert obj_type.type_def is not None

    if not issubclass(obj_type.type_def, Robot):
        raise Arcor2Exception("Not a robot.")

    obj_type.robot_meta = robot.RobotMeta(obj_type.meta.type, obj_type.type_def.robot_type)

    obj_type.robot_meta.features.move_to_pose = _feature(obj_type.type_def, Robot.move_to_pose.__name__)
    obj_type.robot_meta.features.move_to_joints = _feature(obj_type.type_def, Robot.move_to_joints.__name__)
    obj_type.robot_meta.features.stop = _feature(obj_type.type_def, Robot.stop.__name__)

    if issubclass(obj_type.type_def, Robot) and obj_type.type_def.urdf_package_path:
        obj_type.robot_meta.urdf_package_filename = os.path.split(obj_type.type_def.urdf_package_path)[1]


async def stop(robot_id: str) -> None:

    robot_inst = await osa.get_robot_instance(robot_id)

    if not robot_inst.move_in_progress:
        raise Arcor2Exception("Robot is not moving.")

    try:
        await hlp.run_in_executor(robot_inst.stop)
    except NotImplementedError as e:
        raise Arcor2Exception from e


async def check_robot_before_move(robot_id: str) -> None:

    robot_inst = await osa.get_robot_instance(robot_id)
    robot_inst.check_if_ready_to_move()

    if glob.RUNNING_ACTION:

        assert glob.PROJECT
        action = glob.PROJECT.action(glob.RUNNING_ACTION)
        obj_id_str, _ = action.parse_type()

        if robot_id == obj_id_str:
            raise Arcor2Exception("Robot is executing action.")


async def _move_to_pose(robot_id: str, end_effector_id: str, pose: common.Pose, speed: float) -> None:
    # TODO newly connected interface should be notified somehow (general solution for such cases would be great!)

    robot_inst = await osa.get_robot_instance(robot_id, end_effector_id)

    try:
        await hlp.run_in_executor(robot_inst.move_to_pose, end_effector_id, pose, speed)
    except (NotImplementedError, Arcor2Exception) as e:
        glob.logger.error(f"Robot movement failed with: {str(e)}")
        raise Arcor2Exception(str(e)) from e


async def move_to_pose(robot_id: str, end_effector_id: str, pose: common.Pose, speed: float) -> None:

    await notif.broadcast_event(events.RobotMoveToPoseEvent(
        data=events.RobotMoveToPoseData(events.MoveEventType.START, robot_id, end_effector_id, pose)))

    try:
        await _move_to_pose(robot_id, end_effector_id, pose, speed)

    except Arcor2Exception as e:
        await notif.broadcast_event(events.RobotMoveToPoseEvent(
            data=events.RobotMoveToPoseData(events.MoveEventType.FAILED, robot_id, end_effector_id, pose,
                                            message=str(e))))
        return

    await notif.broadcast_event(events.RobotMoveToPoseEvent(
        data=events.RobotMoveToPoseData(events.MoveEventType.END, robot_id, end_effector_id, pose)))


async def move_to_ap_orientation(robot_id: str, end_effector_id: str, pose: common.Pose, speed: float,
                                 orientation_id: str) -> None:

    await notif.broadcast_event(events.RobotMoveToActionPointOrientationEvent(
        data=events.RobotMoveToActionPointOrientationData(
            events.MoveEventType.START, robot_id, end_effector_id, orientation_id)))

    try:
        await _move_to_pose(robot_id, end_effector_id, pose, speed)

    except Arcor2Exception as e:
        await notif.broadcast_event(events.RobotMoveToActionPointOrientationEvent(
            data=events.RobotMoveToActionPointOrientationData(
                events.MoveEventType.FAILED, robot_id, end_effector_id, orientation_id, message=str(e))))
        return

    await notif.broadcast_event(events.RobotMoveToActionPointOrientationEvent(
        data=events.RobotMoveToActionPointOrientationData(
            events.MoveEventType.END, robot_id, end_effector_id, orientation_id)))


async def _move_to_joints(robot_id: str, joints: List[common.Joint], speed: float) -> None:

    # TODO newly connected interface should be notified somehow (general solution for such cases would be great!)

    robot_inst = await osa.get_robot_instance(robot_id)

    try:
        await hlp.run_in_executor(robot_inst.move_to_joints, joints, speed)
    except (NotImplementedError, Arcor2Exception) as e:
        glob.logger.error(f"Robot movement failed with: {str(e)}")
        raise Arcor2Exception(str(e)) from e


async def move_to_joints(robot_id: str, joints: List[common.Joint], speed: float) -> None:

    await notif.broadcast_event(events.RobotMoveToJointsEvent(
        data=events.RobotMoveToJointsData(events.MoveEventType.START, robot_id, joints)))

    try:

        await _move_to_joints(robot_id, joints, speed)

    except Arcor2Exception as e:

        await notif.broadcast_event(events.RobotMoveToJointsEvent(
            data=events.RobotMoveToJointsData(events.MoveEventType.FAILED, robot_id, joints, message=str(e))))

        return

    await notif.broadcast_event(events.RobotMoveToJointsEvent(
        data=events.RobotMoveToJointsData(events.MoveEventType.END, robot_id, joints)))


async def move_to_ap_joints(robot_id: str, joints: List[common.Joint], speed: float, joints_id: str) -> None:

    await notif.broadcast_event(events.RobotMoveToActionPointJointsEvent(
        data=events.RobotMoveToActionPointJointsData(events.MoveEventType.START, robot_id, joints_id)))

    try:

        await _move_to_joints(robot_id, joints, speed)

    except Arcor2Exception as e:

        await notif.broadcast_event(events.RobotMoveToActionPointJointsEvent(
            data=events.RobotMoveToActionPointJointsData(events.MoveEventType.FAILED, robot_id, joints_id,
                                                         message=str(e))))

        return

    await notif.broadcast_event(events.RobotMoveToActionPointJointsEvent(
        data=events.RobotMoveToActionPointJointsData(events.MoveEventType.END, robot_id, joints_id)))
