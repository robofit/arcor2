import asyncio
import inspect
from typing import Any

import arcor2.helpers as hlp
from arcor2.cached import CachedScene
from arcor2.clients import aio_asset as asset
from arcor2.data import common
from arcor2.exceptions import Arcor2Exception
from arcor2.object_types.abstract import MultiArmRobot, Robot
from arcor2_arserver import globals as glob
from arcor2_arserver import logger
from arcor2_arserver import notifications as notif
from arcor2_arserver import objects_actions as osa
from arcor2_arserver.object_types.data import ObjectTypeData
from arcor2_arserver.object_types.source import function_implemented
from arcor2_arserver_data import events as sevts
from arcor2_arserver_data.robot import RobotMeta


class RobotPoseException(Arcor2Exception):
    pass


class SingleArmRobotException(Arcor2Exception):
    pass


def prepare_args(robot_inst: Robot, args: list[Any], arm_id: None | str) -> list[Any]:

    if isinstance(robot_inst, MultiArmRobot):
        args.append(arm_id)
    elif arm_id:
        raise SingleArmRobotException("Single arm robot.")

    return args


async def get_arms(robot_inst: Robot) -> set[str]:
    """
    :param robot_inst:
    :return: IDs of existing arms.
    """

    if not isinstance(robot_inst, MultiArmRobot):
        raise SingleArmRobotException(f"{robot_inst.__class__.__name__} has only one arm.")

    return await hlp.run_in_executor(robot_inst.get_arm_ids)


async def get_end_effectors(robot_inst: Robot, arm_id: None | str) -> set[str]:
    """
    :param robot_inst:
    :return: IDs of existing end effectors.
    """

    return await hlp.run_in_executor(robot_inst.get_end_effectors_ids, *prepare_args(robot_inst, [], arm_id))


async def get_grippers(robot_inst: Robot, arm_id: None | str) -> set[str]:
    """
    :param robot_inst:
    :return: IDs of existing grippers.
    """

    return await hlp.run_in_executor(robot_inst.grippers, *prepare_args(robot_inst, [], arm_id))


async def get_suctions(robot_inst: Robot, arm_id: None | str) -> set[str]:
    """
    :param robot_inst:
    :return: IDs of existing suctions.
    """

    return await hlp.run_in_executor(robot_inst.suctions, *prepare_args(robot_inst, [], arm_id))


async def get_pose_and_joints(
    robot_inst: Robot, end_effector: str, arm_id: None | str
) -> tuple[common.Pose, list[common.Joint]]:

    return await asyncio.gather(
        hlp.run_in_executor(robot_inst.get_end_effector_pose, *prepare_args(robot_inst, [end_effector], arm_id)),
        hlp.run_in_executor(robot_inst.robot_joints, *prepare_args(robot_inst, [False], arm_id)),
    )


async def get_end_effector_pose(robot_inst: Robot, end_effector: str, arm_id: None | str) -> common.Pose:
    """
    :param robot_inst:
    :param end_effector:
    :return: Global pose
    """

    return await hlp.run_in_executor(
        robot_inst.get_end_effector_pose, *prepare_args(robot_inst, [end_effector], arm_id)
    )


async def get_robot_joints(robot_inst: Robot, arm_id: None | str, include_gripper: bool = False) -> list[common.Joint]:
    """
    :param robot_inst:
    :return: List of joints
    """

    return await hlp.run_in_executor(robot_inst.robot_joints, *prepare_args(robot_inst, [include_gripper], arm_id))


def _feature(type_def: type[Robot], method_name: str, base_class: type[Robot]) -> bool:

    assert glob.OBJECT_TYPES

    method = getattr(type_def, method_name)
    where_it_is_defined = glob.OBJECT_TYPES.get(method.__qualname__.split(".")[0], None)

    if where_it_is_defined is None:
        raise Arcor2Exception(f"Can't get origin for {type_def.__name__}/{method_name}.")

    if where_it_is_defined.type_def is None or where_it_is_defined.ast is None:
        raise Arcor2Exception(
            f"Origin {where_it_is_defined.meta.type} for {type_def.__name__}/{method_name} is disabled."
        )

    logger.debug(
        f"Processing {type_def.__name__}/{method_name} "
        f"(defined in {where_it_is_defined.type_def.__name__}), with base class {base_class.__name__}."
    )

    if where_it_is_defined.type_def is base_class or where_it_is_defined.meta.disabled:
        # all of the "feature" methods are abstract in the base class and have to be implemented for the concrete robot
        return False

    if not function_implemented(where_it_is_defined.ast, method_name):
        logger.debug(f"{type_def.__name__}/{method_name} not implemented.")
        return False

    sign = inspect.signature(getattr(where_it_is_defined.type_def, method_name))
    if not (res := inspect.signature(getattr(base_class, method_name)) == sign):
        logger.debug(f"{type_def.__name__}/{method_name} has invalid signature.")
    return res


async def get_robot_meta(obj_type: ObjectTypeData) -> None:

    if obj_type.meta.disabled:
        raise Arcor2Exception("Disabled object type.")

    assert obj_type.type_def is not None

    if not issubclass(obj_type.type_def, Robot):
        raise Arcor2Exception("Not a robot.")

    obj_type.robot_meta = RobotMeta(
        obj_type.meta.type, obj_type.type_def.robot_type, issubclass(obj_type.type_def, MultiArmRobot)
    )

    # TODO fix mypy issue 'Can only assign concrete classes to a variable of type "Type[Robot]"'
    base_class: type[Robot] = MultiArmRobot if obj_type.robot_meta.multi_arm else Robot  # type: ignore

    # TODO automate this somehow
    obj_type.robot_meta.features.move_to_pose = _feature(obj_type.type_def, Robot.move_to_pose.__name__, base_class)
    obj_type.robot_meta.features.move_to_joints = _feature(obj_type.type_def, Robot.move_to_joints.__name__, base_class)
    obj_type.robot_meta.features.stop = _feature(obj_type.type_def, Robot.stop.__name__, base_class)
    obj_type.robot_meta.features.inverse_kinematics = _feature(
        obj_type.type_def, Robot.inverse_kinematics.__name__, base_class
    )
    obj_type.robot_meta.features.forward_kinematics = _feature(
        obj_type.type_def, Robot.forward_kinematics.__name__, base_class
    )
    obj_type.robot_meta.features.hand_teaching = _feature(
        obj_type.type_def, Robot.set_hand_teaching_mode.__name__, base_class
    )

    if urdf_name := obj_type.type_def.urdf_package_name:

        if not await asset.asset_exists(urdf_name):
            logger.error(f"URDF package {urdf_name} for {obj_type.meta.type} does not exist.")
        else:
            obj_type.robot_meta.urdf_package_filename = urdf_name
            # TODO check if URDF is valid?

    logger.debug(obj_type.robot_meta)


async def stop(robot_inst: Robot) -> None:

    if not robot_inst.move_in_progress:
        raise Arcor2Exception("Robot is not moving.")

    await hlp.run_in_executor(robot_inst.stop)


async def ik(
    robot_inst: Robot,
    end_effector_id: str,
    arm_id: None | str,
    pose: common.Pose,
    start_joints: None | list[common.Joint] = None,
    avoid_collisions: bool = True,
) -> list[common.Joint]:

    return await hlp.run_in_executor(
        robot_inst.inverse_kinematics,
        *prepare_args(robot_inst, [end_effector_id, pose, start_joints, avoid_collisions], arm_id),
    )


async def fk(robot_inst: Robot, end_effector_id: str, arm_id: None | str, joints: list[common.Joint]) -> common.Pose:

    return await hlp.run_in_executor(
        robot_inst.forward_kinematics, *prepare_args(robot_inst, [end_effector_id, joints], arm_id)
    )


async def check_reachability(
    scene: CachedScene,
    robot_inst: Robot,
    end_effector_id: str,
    arm_id: None | str,
    pose: common.Pose,
    safe: bool = True,
) -> None:

    otd = osa.get_obj_type_data(scene, robot_inst.id)
    if otd.robot_meta and otd.robot_meta.features.inverse_kinematics:
        try:
            await ik(robot_inst, end_effector_id, arm_id, pose, avoid_collisions=safe)
        except Robot.KinematicsException:
            raise Arcor2Exception("Unreachable pose.")
        except Arcor2Exception as e:
            logger.exception("Failed to check reachability.")
            raise Arcor2Exception("Error on getting IK.") from e


async def check_robot_before_move(robot_inst: Robot) -> None:

    robot_inst.check_if_ready_to_move()

    if glob.RUNNING_ACTION:

        assert glob.LOCK.project
        action = glob.LOCK.project.action(glob.RUNNING_ACTION)
        obj_id_str, _ = action.parse_type()

        if robot_inst.id == obj_id_str:
            raise Arcor2Exception("Robot is executing action.")


async def _move_to_pose(
    robot_inst: Robot,
    end_effector_id: str,
    arm_id: None | str,
    pose: common.Pose,
    speed: float,
    safe: bool,
    linear: bool,
) -> None:
    # TODO newly connected interface should be notified somehow (general solution for such cases would be great!)

    try:
        await hlp.run_in_executor(
            robot_inst.move_to_pose, *prepare_args(robot_inst, [end_effector_id, pose, speed, safe, linear], arm_id)
        )
    except Arcor2Exception as e:
        logger.error(f"Robot movement failed with: {str(e)}")
        raise


async def move_to_pose(
    robot_inst: Robot,
    end_effector_id: str,
    arm_id: None | str,
    pose: common.Pose,
    speed: float,
    safe: bool,
    linear: bool,
    lock_owner: None | str = None,
) -> None:

    try:
        Data = sevts.r.RobotMoveToPose.Data

        await notif.broadcast_event(
            sevts.r.RobotMoveToPose(
                Data(Data.MoveEventType.START, robot_inst.id, end_effector_id, pose, safe, linear, arm_id=arm_id)
            )
        )

        try:
            await _move_to_pose(robot_inst, end_effector_id, arm_id, pose, speed, safe, linear)

        except Arcor2Exception as e:
            await notif.broadcast_event(
                sevts.r.RobotMoveToPose(
                    Data(Data.MoveEventType.FAILED, robot_inst.id, end_effector_id, pose, safe, linear, str(e), arm_id)
                )
            )
            return

        await notif.broadcast_event(
            sevts.r.RobotMoveToPose(
                Data(Data.MoveEventType.END, robot_inst.id, end_effector_id, pose, safe, linear, arm_id=arm_id)
            )
        )
    finally:
        if lock_owner:
            await glob.LOCK.write_unlock(robot_inst.id, lock_owner)


async def move_to_ap_orientation(
    robot_inst: Robot,
    end_effector_id: str,
    arm_id: None | str,
    pose: common.Pose,
    speed: float,
    orientation_id: str,
    safe: bool,
    linear: bool,
) -> None:

    Data = sevts.r.RobotMoveToActionPointOrientation.Data

    await notif.broadcast_event(
        sevts.r.RobotMoveToActionPointOrientation(
            Data(Data.MoveEventType.START, robot_inst.id, end_effector_id, orientation_id, safe, linear, arm_id=arm_id)
        )
    )

    try:
        await _move_to_pose(robot_inst, end_effector_id, arm_id, pose, speed, safe, linear)

    except Arcor2Exception as e:
        await notif.broadcast_event(
            sevts.r.RobotMoveToActionPointOrientation(
                Data(
                    Data.MoveEventType.FAILED,
                    robot_inst.id,
                    end_effector_id,
                    orientation_id,
                    safe,
                    linear,
                    str(e),
                    arm_id,
                )
            )
        )
        return

    await notif.broadcast_event(
        sevts.r.RobotMoveToActionPointOrientation(
            Data(Data.MoveEventType.END, robot_inst.id, end_effector_id, orientation_id, safe, linear, arm_id=arm_id)
        )
    )


async def _move_to_joints(
    robot_inst: Robot, joints: list[common.Joint], speed: float, safe: bool, arm_id: None | str
) -> None:

    # TODO newly connected interface should be notified somehow (general solution for such cases would be great!)

    try:
        await hlp.run_in_executor(robot_inst.move_to_joints, *prepare_args(robot_inst, [joints, speed, safe], arm_id))
    except Arcor2Exception as e:
        logger.error(f"Robot movement failed with: {str(e)}")
        raise


async def move_to_joints(
    robot_inst: Robot,
    joints: list[common.Joint],
    speed: float,
    safe: bool,
    arm_id: None | str,
    lock_owner: None | str = None,
) -> None:

    try:
        Data = sevts.r.RobotMoveToJoints.Data

        await notif.broadcast_event(
            sevts.r.RobotMoveToJoints(Data(Data.MoveEventType.START, robot_inst.id, joints, safe, arm_id=arm_id))
        )

        try:

            await _move_to_joints(robot_inst, joints, speed, safe, arm_id)

        except Arcor2Exception as e:

            await notif.broadcast_event(
                sevts.r.RobotMoveToJoints(
                    Data(Data.MoveEventType.FAILED, robot_inst.id, joints, safe, str(e), arm_id=arm_id)
                )
            )

            return

        await notif.broadcast_event(
            sevts.r.RobotMoveToJoints(Data(Data.MoveEventType.END, robot_inst.id, joints, safe, arm_id=arm_id))
        )
    finally:
        if lock_owner:
            await glob.LOCK.write_unlock(robot_inst.id, lock_owner)


async def move_to_ap_joints(
    robot_inst: Robot,
    joints: list[common.Joint],
    speed: float,
    joints_id: str,
    safe: bool,
    arm_id: None | str,
) -> None:

    Data = sevts.r.RobotMoveToActionPointJoints.Data

    await notif.broadcast_event(
        sevts.r.RobotMoveToActionPointJoints(
            Data(Data.MoveEventType.START, robot_inst.id, joints_id, safe, arm_id=arm_id)
        )
    )

    try:

        await _move_to_joints(robot_inst, joints, speed, safe, arm_id)

    except Arcor2Exception as e:

        await notif.broadcast_event(
            sevts.r.RobotMoveToActionPointJoints(
                Data(Data.MoveEventType.FAILED, robot_inst.id, joints_id, safe, str(e), arm_id)
            )
        )

        return

    await notif.broadcast_event(
        sevts.r.RobotMoveToActionPointJoints(
            Data(Data.MoveEventType.END, robot_inst.id, joints_id, safe, arm_id=arm_id)
        )
    )


async def check_eef_arm(robot_inst: Robot, arm_id: None | str, eef_id: None | str = None) -> None:

    if isinstance(robot_inst, MultiArmRobot):
        if not arm_id:
            raise Arcor2Exception("Arm has to be specified.")

        if eef_id is not None and eef_id not in await hlp.run_in_executor(robot_inst.get_end_effectors_ids, arm_id):
            raise Arcor2Exception("Unknown end effector.")

        return

    if arm_id:
        raise Arcor2Exception("Arm should not be specified.")

    if eef_id is not None and eef_id not in await hlp.run_in_executor(robot_inst.get_end_effectors_ids):
        raise Arcor2Exception("Unknown end effector.")
