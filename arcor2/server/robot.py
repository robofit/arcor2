

async def get_end_effector_pose(robot_id: str, end_effector: str) -> Pose:
    """
    :param robot_id:
    :param end_effector:
    :return: Global pose
    """

    robot_inst = await osa.get_robot_instance(robot_id, end_effector)

    if isinstance(robot_inst, Robot):

        try:
            return await hlp.run_in_executor(robot_inst.get_end_effector_pose, end_effector)
        except NotImplementedError:
            raise RobotPoseException("The robot does not support getting pose.")

    elif isinstance(robot_inst, RobotService):

        try:
            return await hlp.run_in_executor(robot_inst.get_end_effector_pose, robot_id, end_effector)
        except NotImplementedError:
            raise RobotPoseException("The robot does not support getting pose.")

    else:
        raise Arcor2Exception("Not a robot instance.")


async def get_robot_joints(robot_id: str) -> List[Joint]:
    """
    :param robot_id:
    :return: List of joints
    """

    robot_inst = await osa.get_robot_instance(robot_id)

    if isinstance(robot_inst, Robot):

        try:
            return await hlp.run_in_executor(robot_inst.robot_joints)
        except NotImplementedError:
            raise RobotPoseException("The robot does not support getting joints.")

    elif isinstance(robot_inst, RobotService):

        try:
            return await hlp.run_in_executor(robot_inst.robot_joints, robot_id)
        except NotImplementedError:
            raise RobotPoseException("The robot does not support getting joints.")

    else:
        raise Arcor2Exception("Not a robot instance.")


async def _get_robot_meta(robot_type: Union[Type[Robot], Type[RobotService]]) -> None:

    meta = RobotMeta(robot_type.__name__)
    meta.features.focus = hasattr(robot_type, "focus")  # TODO more sophisticated test? (attr(s) and return value?)
    ROBOT_META[robot_type.__name__] = meta