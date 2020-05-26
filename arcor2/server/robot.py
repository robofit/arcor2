from typing import List, Union, Type, Optional, Set
import os

from arcor2.data.common import Pose, Joint
from arcor2.data.robot import RobotMeta
from arcor2.exceptions import Arcor2Exception
import arcor2.helpers as hlp
from arcor2.object_types import Robot, Generic
from arcor2.services import RobotService

from arcor2.server import objects_services_actions as osa, globals as glob


class RobotPoseException(Arcor2Exception):
    pass


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


async def get_end_effectors(robot_id: str) -> Set[str]:
    """
    :param robot_id:
    :return: IDs of existing end effectors.
    """

    robot_inst = await osa.get_robot_instance(robot_id)

    if isinstance(robot_inst, Robot):
        return await hlp.run_in_executor(robot_inst.get_end_effectors_ids)
    else:
        return await hlp.run_in_executor(robot_inst.get_end_effectors_ids, robot_id)


async def get_grippers(robot_id: str) -> Set[str]:
    """
    :param robot_id:
    :return: IDs of existing grippers.
    """

    robot_inst = await osa.get_robot_instance(robot_id)

    if isinstance(robot_inst, Robot):
        return await hlp.run_in_executor(robot_inst.grippers)
    else:
        return await hlp.run_in_executor(robot_inst.grippers, robot_id)


async def get_suctions(robot_id: str) -> Set[str]:
    """
    :param robot_id:
    :return: IDs of existing suctions.
    """

    robot_inst = await osa.get_robot_instance(robot_id)

    if isinstance(robot_inst, Robot):
        return await hlp.run_in_executor(robot_inst.suctions)
    else:
        return await hlp.run_in_executor(robot_inst.suctions, robot_id)


async def get_end_effector_pose(robot_id: str, end_effector: str) -> Pose:
    """
    :param robot_id:
    :param end_effector:
    :return: Global pose
    """

    robot_inst = await osa.get_robot_instance(robot_id, end_effector)

    if isinstance(robot_inst, Robot):
        return await hlp.run_in_executor(robot_inst.get_end_effector_pose, end_effector)
    else:
        return await hlp.run_in_executor(robot_inst.get_end_effector_pose, robot_id, end_effector)


async def get_robot_joints(robot_id: str) -> List[Joint]:
    """
    :param robot_id:
    :return: List of joints
    """

    robot_inst = await osa.get_robot_instance(robot_id)

    if isinstance(robot_inst, Robot):
        return await hlp.run_in_executor(robot_inst.robot_joints)
    else:
        return await hlp.run_in_executor(robot_inst.robot_joints, robot_id)


async def get_robot_meta(robot_type: Union[Type[Robot], Type[RobotService]]) -> None:

    meta = RobotMeta(robot_type.__name__)
    meta.features.focus = hasattr(robot_type, "focus")  # TODO more sophisticated test? (attr(s) and return value?)

    if issubclass(robot_type, Robot) and robot_type.urdf_package_path:
        meta.urdf_package_filename = os.path.split(robot_type.urdf_package_path)[1]

    glob.ROBOT_META[robot_type.__name__] = meta
