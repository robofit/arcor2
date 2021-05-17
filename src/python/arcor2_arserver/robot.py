import asyncio
import inspect
from ast import AST
from typing import List, Optional, Set, Tuple, Type

import arcor2.helpers as hlp
from arcor2.cached import CachedScene
from arcor2.data import common
from arcor2.exceptions import Arcor2Exception
from arcor2.object_types.abstract import Robot
from arcor2_arserver import globals as glob
from arcor2_arserver import notifications as notif
from arcor2_arserver import objects_actions as osa
from arcor2_arserver.object_types.data import ObjectTypeData
from arcor2_arserver.object_types.source import function_implemented
from arcor2_arserver_data import events as sevts
from arcor2_arserver_data.robot import RobotMeta


class RobotPoseException(Arcor2Exception):
    pass


async def get_end_effectors(robot_inst: Robot) -> Set[str]:
    """
    :param robot_id:
    :return: IDs of existing end effectors.
    """

    return await hlp.run_in_executor(robot_inst.get_end_effectors_ids)


async def get_grippers(robot_inst: Robot) -> Set[str]:
    """
    :param robot_id:
    :return: IDs of existing grippers.
    """

    return await hlp.run_in_executor(robot_inst.grippers)


async def get_suctions(robot_inst: Robot) -> Set[str]:
    """
    :param robot_id:
    :return: IDs of existing suctions.
    """

    return await hlp.run_in_executor(robot_inst.suctions)


async def get_pose_and_joints(robot_inst: Robot, end_effector: str) -> Tuple[common.Pose, List[common.Joint]]:

    return await asyncio.gather(
        hlp.run_in_executor(robot_inst.get_end_effector_pose, end_effector),
        hlp.run_in_executor(robot_inst.robot_joints),
    )


async def get_end_effector_pose(robot_inst: Robot, end_effector: str) -> common.Pose:
    """
    :param robot_id:
    :param end_effector:
    :return: Global pose
    """

    return await hlp.run_in_executor(robot_inst.get_end_effector_pose, end_effector)


async def get_robot_joints(robot_inst: Robot) -> List[common.Joint]:
    """
    :param robot_id:
    :return: List of joints
    """

    return await hlp.run_in_executor(robot_inst.robot_joints)


def feature(tree: AST, robot_type: Type[Robot], func_name: str) -> bool:

    if not function_implemented(tree, func_name):
        glob.logger.debug(f"robot_type {robot_type.__name__}, func_name {func_name} not implemented.")
        return False

    sign = inspect.signature(getattr(robot_type, func_name))
    res = inspect.signature(getattr(Robot, func_name)) == sign
    if not res:
        glob.logger.debug(f"robot_type {robot_type.__name__}, func_name {func_name} has invalid signature.")
    return res


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


async def get_robot_meta(obj_type: ObjectTypeData) -> None:

    if obj_type.meta.disabled:
        raise Arcor2Exception("Disabled object type.")

    assert obj_type.type_def is not None

    if not issubclass(obj_type.type_def, Robot):
        raise Arcor2Exception("Not a robot.")

    obj_type.robot_meta = RobotMeta(obj_type.meta.type, obj_type.type_def.robot_type)

    # TODO automate this somehow
    obj_type.robot_meta.features.move_to_pose = _feature(obj_type.type_def, Robot.move_to_pose.__name__)
    obj_type.robot_meta.features.move_to_joints = _feature(obj_type.type_def, Robot.move_to_joints.__name__)
    obj_type.robot_meta.features.stop = _feature(obj_type.type_def, Robot.stop.__name__)
    obj_type.robot_meta.features.inverse_kinematics = _feature(obj_type.type_def, Robot.inverse_kinematics.__name__)
    obj_type.robot_meta.features.forward_kinematics = _feature(obj_type.type_def, Robot.forward_kinematics.__name__)
    obj_type.robot_meta.features.hand_teaching = _feature(obj_type.type_def, Robot.set_hand_teaching_mode.__name__)

    if issubclass(obj_type.type_def, Robot) and obj_type.type_def.urdf_package_name:
        obj_type.robot_meta.urdf_package_filename = obj_type.type_def.urdf_package_name


async def stop(robot_inst: Robot) -> None:

    if not robot_inst.move_in_progress:
        raise Arcor2Exception("Robot is not moving.")

    await hlp.run_in_executor(robot_inst.stop)


async def ik(
    robot_inst: Robot,
    end_effector_id: str,
    pose: common.Pose,
    start_joints: Optional[List[common.Joint]] = None,
    avoid_collisions: bool = True,
) -> List[common.Joint]:

    return await hlp.run_in_executor(
        robot_inst.inverse_kinematics, end_effector_id, pose, start_joints, avoid_collisions
    )


async def fk(robot_inst: Robot, end_effector_id: str, joints: List[common.Joint]) -> common.Pose:

    return await hlp.run_in_executor(robot_inst.forward_kinematics, end_effector_id, joints)


async def check_reachability(
    scene: CachedScene, robot_inst: Robot, end_effector_id: str, pose: common.Pose, safe: bool = True
) -> None:

    otd = osa.get_obj_type_data(scene, robot_inst.id)
    if otd.robot_meta and otd.robot_meta.features.inverse_kinematics:
        try:
            await ik(robot_inst, end_effector_id, pose, avoid_collisions=safe)
        except Arcor2Exception as e:
            raise Arcor2Exception("Unreachable pose.") from e


async def check_robot_before_move(robot_inst: Robot) -> None:

    robot_inst.check_if_ready_to_move()

    if glob.RUNNING_ACTION:

        assert glob.LOCK.project
        action = glob.LOCK.project.action(glob.RUNNING_ACTION)
        obj_id_str, _ = action.parse_type()

        if robot_inst.id == obj_id_str:
            raise Arcor2Exception("Robot is executing action.")


async def _move_to_pose(robot_inst: Robot, end_effector_id: str, pose: common.Pose, speed: float, safe: bool) -> None:
    # TODO newly connected interface should be notified somehow (general solution for such cases would be great!)

    try:
        await hlp.run_in_executor(robot_inst.move_to_pose, end_effector_id, pose, speed, safe)
    except Arcor2Exception as e:
        glob.logger.error(f"Robot movement failed with: {str(e)}")
        raise


async def move_to_pose(
    robot_inst: Robot,
    end_effector_id: str,
    pose: common.Pose,
    speed: float,
    safe: bool,
    lock_owner: Optional[str] = None,
) -> None:

    try:
        Data = sevts.r.RobotMoveToPose.Data

        await notif.broadcast_event(
            sevts.r.RobotMoveToPose(Data(Data.MoveEventType.START, robot_inst.id, end_effector_id, pose, safe))
        )

        try:
            await _move_to_pose(robot_inst, end_effector_id, pose, speed, safe)

        except Arcor2Exception as e:
            await notif.broadcast_event(
                sevts.r.RobotMoveToPose(
                    Data(Data.MoveEventType.FAILED, robot_inst.id, end_effector_id, pose, safe, message=str(e))
                )
            )
            return

        await notif.broadcast_event(
            sevts.r.RobotMoveToPose(Data(Data.MoveEventType.END, robot_inst.id, end_effector_id, pose, safe))
        )
    finally:
        if lock_owner:
            await glob.LOCK.write_unlock(robot_inst.id, lock_owner)


async def move_to_ap_orientation(
    robot_inst: Robot, end_effector_id: str, pose: common.Pose, speed: float, orientation_id: str, safe: bool
) -> None:

    Data = sevts.r.RobotMoveToActionPointOrientation.Data

    await notif.broadcast_event(
        sevts.r.RobotMoveToActionPointOrientation(
            Data(Data.MoveEventType.START, robot_inst.id, end_effector_id, orientation_id, safe)
        )
    )

    try:
        await _move_to_pose(robot_inst, end_effector_id, pose, speed, safe)

    except Arcor2Exception as e:
        await notif.broadcast_event(
            sevts.r.RobotMoveToActionPointOrientation(
                Data(Data.MoveEventType.FAILED, robot_inst.id, end_effector_id, orientation_id, safe, message=str(e))
            )
        )
        return

    await notif.broadcast_event(
        sevts.r.RobotMoveToActionPointOrientation(
            Data(Data.MoveEventType.END, robot_inst.id, end_effector_id, orientation_id, safe)
        )
    )


async def _move_to_joints(robot_inst: Robot, joints: List[common.Joint], speed: float, safe: bool) -> None:

    # TODO newly connected interface should be notified somehow (general solution for such cases would be great!)

    try:
        await hlp.run_in_executor(robot_inst.move_to_joints, joints, speed, safe)
    except Arcor2Exception as e:
        glob.logger.error(f"Robot movement failed with: {str(e)}")
        raise


async def move_to_joints(
    robot_inst: Robot, joints: List[common.Joint], speed: float, safe: bool, lock_owner: Optional[str] = None
) -> None:

    try:
        Data = sevts.r.RobotMoveToJoints.Data

        await notif.broadcast_event(
            sevts.r.RobotMoveToJoints(Data(Data.MoveEventType.START, robot_inst.id, joints, safe))
        )

        try:

            await _move_to_joints(robot_inst, joints, speed, safe)

        except Arcor2Exception as e:

            await notif.broadcast_event(
                sevts.r.RobotMoveToJoints(Data(Data.MoveEventType.FAILED, robot_inst.id, joints, safe, message=str(e)))
            )

            return

        await notif.broadcast_event(
            sevts.r.RobotMoveToJoints(Data(Data.MoveEventType.END, robot_inst.id, joints, safe))
        )
    finally:
        if lock_owner:
            await glob.LOCK.write_unlock(robot_inst.id, lock_owner)


async def move_to_ap_joints(
    robot_inst: Robot, joints: List[common.Joint], speed: float, joints_id: str, safe: bool
) -> None:

    Data = sevts.r.RobotMoveToActionPointJoints.Data

    await notif.broadcast_event(
        sevts.r.RobotMoveToActionPointJoints(Data(Data.MoveEventType.START, robot_inst.id, joints_id, safe))
    )

    try:

        await _move_to_joints(robot_inst, joints, speed, safe)

    except Arcor2Exception as e:

        await notif.broadcast_event(
            sevts.r.RobotMoveToActionPointJoints(
                Data(Data.MoveEventType.FAILED, robot_inst.id, joints_id, safe, message=str(e))
            )
        )

        return

    await notif.broadcast_event(
        sevts.r.RobotMoveToActionPointJoints(Data(Data.MoveEventType.END, robot_inst.id, joints_id, safe))
    )
